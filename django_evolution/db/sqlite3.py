"""Evolution operations backend for SQLite."""

from __future__ import unicode_literals

from collections import OrderedDict

from django.db import models
from django.db.backends.sqlite3.base import Database

from django_evolution.compat import six
from django_evolution.compat.db import (create_index_name,
                                        sql_indexes_for_model)
from django_evolution.compat.models import (get_remote_field,
                                            get_remote_field_model)
from django_evolution.db.common import (AlterTableSQLResult,
                                        BaseEvolutionOperations,
                                        SQLResult)
from django_evolution.utils.sql import NewTransactionSQL, NoTransactionSQL


TEMP_TABLE_NAME = 'TEMP_TABLE'


class SQLiteAlterTableSQLResult(AlterTableSQLResult):
    """Represents SQL statements used to rebuild a table on SQLite.

    Unlike most databases, SQLite doesn't offer typical ALTER TABLE support,
    instead requiring a full table rebuild and data transfer. This class
    handles that process, allowing operations for the rebuild (adding,
    deleting, or changing columns) to be batched together.

    The rebuild uses the step-by-step instructions recommended by SQLite. It
    creates a new table with the desired schema, copies all data from the old
    table, drops the old table, and then renames the new table over.

    It can also update the newly-populated rows in the new table with new
    initial data, if needed by a new column.
    """

    def to_sql(self):
        """Return a list of SQL statements for the table rebuild.

        Any :py:attr:`alter_table` operations will be collapsed together into
        a single table rebuild.

        Returns:
            list of unicode:
            The list of SQL statements to run for the rebuild.
        """
        evolver = self.evolver
        model = self.model
        connection = evolver.connection
        qn = connection.ops.quote_name
        table_name = model._meta.db_table

        # Calculate some state for the rebuild operations, based on the
        # Alter Table ops that were provided.
        added_fields = []
        deleted_columns = set()
        renamed_columns = {}
        replaced_fields = {}
        added_constraints = []
        new_initial = {}
        reffed_renamed_cols = []
        added_field_db_indexes = []
        dropped_field_db_indexes = []
        needs_rebuild = False
        sql = []

        for item in self.alter_table:
            op = item['op']

            if op == 'ADD COLUMN':
                needs_rebuild = True
                field = item['field']

                if field.db_type(connection=connection) is not None:
                    initial = item['initial']

                    added_fields.append(field)

                    if initial is not None:
                        new_initial[field.column] = initial
            elif op == 'DELETE COLUMN':
                needs_rebuild = True
                deleted_columns.add(item['column'])
            elif op == 'RENAME COLUMN':
                needs_rebuild = True
                old_field = item['old_field']
                new_field = item['new_field']
                old_column = old_field.column
                new_column = new_field.column

                renamed_columns[old_column] = new_field.column
                replaced_fields[old_column] = new_field

                if evolver.is_column_referenced(table_name, old_column):
                    reffed_renamed_cols.append((old_column, new_column))
            elif op == 'MODIFY COLUMN':
                needs_rebuild = True
                field = item['field']
                initial = item['initial']

                replaced_fields[field.column] = field

                if initial is not None:
                    new_initial[field.column] = initial
            elif op == 'CHANGE COLUMN TYPE':
                needs_rebuild = True
                old_field = item['old_field']
                new_field = item['new_field']
                column = old_field.column

                replaced_fields[column] = new_field
            elif op == 'ADD CONSTRAINTS':
                needs_rebuild = True
                added_constraints = item['constraints']
            elif op == 'REBUILD':
                # We're just rebuilding, not changing anything about it.
                # This is used to get rid of auto-indexes from SQLite.
                needs_rebuild = True
            elif op == 'ADD DB INDEX':
                added_field_db_indexes.append(item['field'])
            elif op == 'DROP DB INDEX':
                dropped_field_db_indexes.append(item['field'])
            else:
                raise ValueError('%s is not a valid Alter Table op for SQLite'
                                 % op)

        for field in dropped_field_db_indexes:
            sql += self.normalize_sql(evolver.drop_index(model, field))

        if not needs_rebuild:
            # We don't have any operations requiring a full table rebuild.
            # We may have indexes to add (which would normally be added
            # along with the rebuild).
            for field in added_field_db_indexes:
                sql += self.normalize_sql(evolver.create_index(model, field))

            return self.pre_sql + self.sql + sql + self.post_sql

        # Remove any Generic Fields.
        old_fields = [
            _field
            for _field in model._meta.local_fields
            if _field.db_type(connection=connection) is not None
        ]

        new_fields = [
            replaced_fields.get(_field.column, _field)
            for _field in old_fields + added_fields
            if _field.column not in deleted_columns
        ]

        field_values = OrderedDict()

        for field in old_fields:
            old_column = field.column

            if old_column not in deleted_columns:
                new_column = renamed_columns.get(old_column, old_column)

                field_values[new_column] = qn(old_column)

        field_initials = []

        # If we have any new fields, add their defaults.
        if new_initial:
            for column, initial in six.iteritems(new_initial):
                # Note that initial will only be None if null=True. Otherwise,
                # it will be set to a user-defined callable or the default
                # AddFieldInitialCallback, which will raise an exception in
                # common code before we get too much further.
                if initial is not None:
                    initial, embed_initial = evolver.normalize_initial(initial)

                    if embed_initial:
                        field_values[column] = initial
                    else:
                        field_initials.append(initial)

                        if column in field_values:
                            field_values[column] = \
                                'coalesce(%s, %%s)' % qn(column)
                        else:
                            field_values[column] = '%s'

        # The SQLite documentation defines the steps that should be taken to
        # safely alter the schema for a table. Unlike most types of databases,
        # SQLite doesn't provide a general ALTER TABLE that can modify any
        # part of the table, so for most things, we require a full table
        # rebuild, and it must be done correctly.
        #
        # Step 1: Create a temporary table representing the new table
        #         schema. This will be temporary, and we don't need to worry
        #         about any indexes yet. Later, this will become the new
        #         table.
        columns_sql = []
        columns_sql_params = []

        for field in new_fields:
            if not isinstance(field, models.ManyToManyField):
                schema = evolver.build_column_schema(model=model,
                                                     field=field)

                columns_sql.append(
                    '%s %s %s'
                    % (qn(schema['name']),
                       schema['db_type'],
                       ' '.join(schema['definition'])))
                columns_sql_params += schema['definition_sql_params']

        constraints_sql = []

        if added_constraints:
            # Django >= 2.2
            with connection.schema_editor(collect_sql=True) as schema_editor:
                for constraint in added_constraints:
                    constraint_sql = constraint.constraint_sql(model,
                                                               schema_editor)

                    if constraint_sql:
                        constraints_sql.append(constraint_sql)

        sql.append((
            'CREATE TABLE %s (%s);'
            % (qn(TEMP_TABLE_NAME),
               ', '.join(columns_sql + constraints_sql)),
            tuple(columns_sql_params),
        ))

        # Step 2: Copy over any data from the old table into the new one.
        sql.append((
            'INSERT INTO %s (%s) SELECT %s FROM %s;'
            % (
                qn(TEMP_TABLE_NAME),
                ', '.join(
                    qn(column)
                    for column in six.iterkeys(field_values)
                ),
                ', '.join(
                    six.text_type(_value)
                    for _value in six.itervalues(field_values)
                ),
                qn(table_name),
            ),
            tuple(field_initials)
        ))

        # Step 3: Drop the old table, making room for us to recreate the
        #         new schema table in its place.
        sql += evolver.delete_table(table_name).to_sql()

        # Step 4: Move over the temp table to the destination table name.
        sql += evolver.rename_table(model=model,
                                    old_db_table=TEMP_TABLE_NAME,
                                    new_db_table=table_name).to_sql()

        # Step 5: Restore any indexes.
        class _Model(object):
            class _meta(object):
                db_table = table_name
                local_fields = new_fields
                db_tablespace = None
                managed = True
                proxy = False
                swapped = False
                index_together = []
                indexes = []

        sql += sql_indexes_for_model(connection, _Model)

        # We've added all the indexes above. Any that were already there
        # will be in the database state. However, if we've *specifically*
        # had requests to add indexes, those ones won't be. We'll need to
        # add them now.
        #
        # The easiest way is to use the same SQL generation functions we'd
        # normally use to generate per-field indexes, since those track
        # database state. We won't actually use the SQL.
        for field in added_field_db_indexes:
            evolver.create_index(model, field)

        if reffed_renamed_cols:
            # One or more tables referenced one or more renamed columns on
            # this table, so now we need to update them.
            #
            # There are issues with renaming columns referenced by a foreign
            # key in SQLite. Historically, we've allowed it, but the reality
            # is that it can result in those foreign keys pointing to the
            # wrong (old) column, causing any foreign key reference checks to
            # fail. This is noticeable with Django 2.2+, which explicitly
            # checks in its schema editor (which we invoke).
            #
            # We don't actually want or need to do a table rebuild on these.
            # SQLite has another trick (and this is recommended in their
            # documentation). We want to go through each of the tables that
            # reference these columns and rewrite their table creation SQL
            # in the sqlite_master table, and then tell SQLite to apply the
            # new schema.
            #
            # This requires that we enable writable schemas and bump up the
            # SQLite schema version for this database. This must be done at
            # the moment we want to run this SQL statement, so we'll be
            # adding this as a dynamic function to run later, rather than
            # hard-coding any SQL now.
            #
            # Most of this can be done in a transaction, but not all. We have
            # to execute much of this in its own transaction, and then write
            # the new schema to disk with a VACUUM outside of a transaction.
            def _update_refs(cursor):
                schema_version = \
                    cursor.execute('PRAGMA schema_version').fetchone()[0]

                refs_template = ' REFERENCES "%s" ("%%s") ' % table_name

                return [
                    NewTransactionSQL(
                        [
                            # Allow us to update the database schema by
                            # manipulating the sqlite_master table.
                            'PRAGMA writable_schema = 1;',
                        ] + [
                            # Update all tables that reference any renamed
                            # columns, setting their references to point to
                            # the new names.
                            ('UPDATE sqlite_master SET sql ='
                             ' replace(sql, %s, %s);',
                             (refs_template % old_column,
                              refs_template % new_column))
                            for old_column, new_column in reffed_renamed_cols
                        ] + [
                            # Tell SQLite that we're done writing the schema,
                            # and give it a new schema version number.
                            ('PRAGMA schema_version = %s;'
                             % (schema_version + 1)),

                            'PRAGMA writable_schema = 0;',

                            # Make sure everything went well. We want to bail
                            # here before we commit the transaction if
                            # anything goes wrong.
                            'PRAGMA integrity_check;',
                        ]
                    ),
                    NoTransactionSQL(['VACUUM;']),
                ]

            sql.append(_update_refs)

        return self.pre_sql + sql + self.sql + self.post_sql


class EvolutionOperations(BaseEvolutionOperations):
    """Evolution operations backend for SQLite."""

    alter_table_sql_result_cls = SQLiteAlterTableSQLResult

    _can_rename_cols_min_version = (3, 26, 0)
    _can_rename_cols = (Database.sqlite_version_info >=
                        _can_rename_cols_min_version)

    def get_deferrable_sql(self):
        """Return the SQL for marking a reference as deferrable.

        Despite SQLite3 supporting this, the Django SQLite3 backend does not
        implement the standard function
        (:py:meth:`BaseDatabaseOperations.deferrable_sql()
        <django.db.backends.base.operations.BaseDatabaseOperations>`) for
        this.

        This provides a value used internally for building references.

        Version Added:
            2.2

        Returns:
            unicode:
            The SQL for marking a reference as deferrable.
        """
        return 'DEFERRABLE INITIALLY DEFERRED'

    def rename_table(self, model, old_db_table, new_db_table):
        """Rename a table.

        Args:
            model (django_evolution.mock_models.MockModel):
                The model representing the table to rename.

            old_db_table (unicode):
                The old table name.

            new_db_table (unicode):
                The new table name.

        Returns:
            django_evolution.db.sql_result.SQLResult:
            The resulting SQL for renaming the table.
        """
        sql_result = SQLResult()

        if old_db_table != new_db_table:
            sql_result.add(self.get_rename_table_sql(model, old_db_table,
                                                     new_db_table))

        return sql_result

    def delete_column(self, model, field):
        """Delete a column from the table.

        Args:
            model (type):
                The :py:class:`~django.db.models.Model` class representing
                the table to delete the column from.

            field (django.db.models.Field):
                The field representing the column to delete.

        Returns:
            django_evolution.db.sql_result.SQLResult:
            The resulting SQL for rebuilding the table.
        """
        return SQLiteAlterTableSQLResult(
            evolver=self,
            model=model,
            alter_table=[
                {
                    'op': 'DELETE COLUMN',
                    'column': field.column,
                },
            ])

    def rename_column(self, model, old_field, new_field):
        """Rename a column on a table.

        Args:
            model (type):
                The :py:class:`~django.db.models.Model` class representing
                the table to rename the column on.

            old_field (django.db.models.Field):
                The field representing the old column.

            new_field (django.db.models.Field):
                The field representing the new column.

        Returns:
            django_evolution.db.sql_result.SQLResult:
            The resulting SQL for rebuilding the table.
        """
        if old_field.column == new_field.column:
            return []

        if self._can_rename_cols:
            qn = self.connection.ops.quote_name

            return SQLResult([
                'ALTER TABLE %s RENAME COLUMN %s TO %s;'
                % (qn(model._meta.db_table),
                   qn(old_field.column),
                   qn(new_field.column))
            ])
        else:
            return SQLiteAlterTableSQLResult(
                evolver=self,
                model=model,
                alter_table=[
                    {
                        'op': 'RENAME COLUMN',
                        'old_field': old_field,
                        'new_field': new_field,
                    },
                ])

    def add_column(self, model, field, initial):
        """Add a column to the table.

        Args:
            model (type):
                The :py:class:`~django.db.models.Model` class representing
                the table to add the column to.

            field (django.db.models.Field):
                The field representing the column to add.

            initial (object);
                The initial data to set for the column. If ``None``, the
                data will not be set.

                This will be required for ``NOT NULL`` columns.

        Returns:
            django_evolution.db.sql_result.SQLResult:
            The resulting SQL for rebuilding the table.
        """
        opts = model._meta
        table_name = opts.db_table

        if field.unique or field.primary_key:
            self.database_state.add_index(
                table_name=table_name,
                index_name=self.get_new_constraint_name(table_name,
                                                        field.column),
                columns=[field.column],
                unique=True)
        elif field.db_index:
            self.database_state.add_index(
                table_name=table_name,
                index_name=create_index_name(self.connection,
                                             table_name,
                                             field_names=[field.name],
                                             col_names=[field.column]),
                columns=[field.column])

        return SQLiteAlterTableSQLResult(
            evolver=self,
            model=model,
            alter_table=[
                {
                    'op': 'ADD COLUMN',
                    'field': field,
                    'initial': initial,
                },
            ])

    def change_column_attr_null(self, model, mutation, field, old_value,
                                new_value):
        """Change a column's NULL flag.

        Args:
            model (type):
                The :py:class:`~django.db.models.Model` class representing
                the table to change the column on.

            mutation (django_evolution.mutations.BaseModelMutation):
                The mutation making this change.

            field (django.db.models.Field):
                The field representing the column to change.

            old_value (bool, unused):
                The old null flag.

            new_value (bool):
                The new null flag.

        Returns:
            django_evolution.db.sql_result.SQLResult:
            The resulting SQL for rebuilding the table.
        """
        return self._change_attribute(model=model,
                                      field=field,
                                      attr_name='null',
                                      new_attr_value=new_value,
                                      initial=mutation.initial)

    def change_column_attr_decimal_type(self, model, mutation, field,
                                        new_max_digits, new_decimal_places):
        """Return SQL for changing a column's decimal_places attribute.

        This is used for :py:class:`~django.db.models.DecimalField` and
        subclasses to change the maximum number of digits or decimal places.
        As these are used together as a column type, they must be considered
        together as one attribute change.

        Args:
            model (type):
                The model class that owns the field.

            mutation (django_evolution.mutations.BaseModelMutation):
                The mutation applying this change.

            field (django.db.models.DecimalField):
                The field being modified.

            new_max_digits (int):
                The new value for ``max_digits``. If ``None``, it wasn't
                provided in the attribute change.

            new_decimal_places (int):
                The new value for ``decimal_places``. If ``None``, it wasn't
                provided in the attribute change.

        Returns:
            django_evolution.db.sql_result.AlterTableSQLResult:
            The SQL for modifying the value.
        """
        if new_max_digits is not None:
            field.max_digits = new_max_digits

        if new_decimal_places is not None:
            field.decimal_places = new_decimal_places

        return SQLiteAlterTableSQLResult(
            evolver=self,
            model=model,
            alter_table=[
                {
                    'op': 'MODIFY COLUMN',
                    'field': field,
                    'initial': None,
                },
            ])

    def change_column_attr_max_length(self, model, mutation, field, old_value,
                                      new_value):
        """Change a column's max length.

        Args:
            model (type):
                The :py:class:`~django.db.models.Model` class representing
                the table to change the column on.

            mutation (django_evolution.mutations.BaseModelMutation):
                The mutation making this change.

            field (django.db.models.Field):
                The field representing the column to change.

            old_value (int, unused):
                The old max length.

            new_value (int, unused):
                The new max length.

        Returns:
            django_evolution.db.sql_result.SQLResult:
            The resulting SQL for rebuilding the table.
        """
        return self._change_attribute(model=model,
                                      field=field,
                                      attr_name='max_length',
                                      new_attr_value=new_value)

    def change_column_type(self, model, old_field, new_field, new_attrs):
        """Return SQL to change the type of a column.

        Version Added:
            2.2

        Args:
            model (type):
                The type of model owning the field.

            old_field (django.db.models.Field):
                The old field.

            new_field (django.db.models.Field):
                The new field.

            new_attrs (dict):
                New attributes set in the
                :py:class:`~django_evolution.mutations.change_field.
                ChangeField`.

        Returns:
            SQLiteAlterTableSQLResult:
            The SQL statements for changing the column type.
        """
        return SQLiteAlterTableSQLResult(
            evolver=self,
            model=model,
            alter_table=[{
                'op': 'CHANGE COLUMN TYPE',
                'old_field': old_field,
                'new_field': new_field,
            }]
        )

    def get_change_unique_sql(self, model, field, new_unique_value,
                              constraint_name, initial):
        """Change a column's unique flag.

        Args:
            model (type):
                The :py:class:`~django.db.models.Model` class representing
                the table to change the column on.

            mutation (django_evolution.mutations.BaseModelMutation):
                The mutation making this change.

            field (django.db.models.Field):
                The field representing the column to change.

            old_value (bool, unused):
                The old unique flag.

            new_value (bool, unused):
                The new unique flag.

        Returns:
            django_evolution.db.sql_result.SQLResult:
            The resulting SQL for rebuilding the table.
        """
        return self._change_attribute(model=model,
                                      field=field,
                                      attr_name='_unique',
                                      new_attr_value=new_unique_value)

    def get_update_table_constraints_sql(self, model, old_constraints,
                                         new_constraints, to_add, to_remove):
        """Return SQL for updating the constraints on a table.

        This will perform a table rebuild, including only any new constraints
        in the new schema.

        Args:
            model (django.db.models.Model):
                The model being changed.

            old_constraints (list of
                             django.db.models.constraints.BaseConstraint):
                The old constraints pre-evolution.

            new_constraints (list of
                             django.db.models.constraints.BaseConstraint):
                The new constraints post-evolution.

            to_add (list of django.db.models.constraints.BaseConstraint):
                A list of new constraints to add to the database that weren't
                set before.

            to_remove (list of django.db.models.constraints.BaseConstraint):
                A list of old constraints to remove from the database that
                aren't set now.

        Returns:
            django_evolution.sql_result.SQLResult:
            The SQL statements for changing the constraints.
        """
        alter_table_items = []

        if to_add:
            alter_table_items.append({
                'op': 'ADD CONSTRAINTS',
                'constraints': new_constraints,
            })
        else:
            assert to_remove

            # We won't be explicitly dropping anything. We'll just be doing
            # a normal table rebuild.
            alter_table_items.append({
                'op': 'REBUILD',
            })

        return SQLiteAlterTableSQLResult(
            evolver=self,
            model=model,
            alter_table=alter_table_items)

    def change_column_attr_db_index(self, model, mutation, field, old_value,
                                    new_value):
        """Return the SQL for creating/dropping indexes for a column.

        If setting ``db_index=True``, SQL for generating the index will be
        returned immediately.

        If setting ``db_index=False``, the dropping of the index will be
        scheduled as an Alter Table operation, ensuring it's dropped
        immediately (and cached/queued database index state updated) before the
        table is rebuilt, never later.

        Version Added:
            2.3

        Args:
            model (django.db.models.Model):
                The model being changed.

            mutation (django_evolution.mutations.BaseModelMutation):
                The mutation applying this change.

            field (django.db.models.DecimalField):
                The field being modified.

            old_value (bool):
                The old value for ``db_index``.

            new_value (bool):
                The new value for ``db_index``.

        Returns:
            django_evolution.db.sql_result.SQLResult:
            The resulting SQL for creating the index or scheduling a drop.
        """
        field.db_index = new_value

        if new_value:
            op = 'ADD DB INDEX'
        else:
            op = 'DROP DB INDEX'

        return SQLiteAlterTableSQLResult(
            evolver=self,
            model=model,
            alter_table=[
                {
                    'op': op,
                    'field': field,
                },
            ])

    def get_drop_unique_constraint_sql(self, model, index_name):
        """Return SQL for dropping unique constraints.

        Args:
            model (type):
                The :py:class:`~django.db.models.Model` class representing
                the table to drop unique constraints on.

            index_name (unicode):
                The name of the unique constraint index to drop.

        Returns:
            django_evolution.db.sql_result.SQLResult:
            The resulting SQL for rebuilding the table.
        """
        if index_name.startswith('sqlite_autoindex'):
            # This is an index generated by SQLite, and cannot be deleted
            # explicitly without a full table rebuild. These are generated
            # on Django 1.8 and lower for any unique_together constraints.
            return SQLiteAlterTableSQLResult(
                evolver=self,
                model=model,
                alter_table=[
                    {
                        'op': 'REBUILD',
                    },
                ])
        else:
            # This is a normal, explicitly-created index. We should be able
            # to drop it with a standard DROP INDEX statement.
            #
            # We should get these by default for tables created on Django 1.9
            # and later.
            return (
                super(EvolutionOperations, self)
                .get_drop_unique_constraint_sql(model, index_name)
            )

    def get_indexes_for_table(self, table_name):
        """Return all known indexes on a table.

        This is a fallback used only on Django 1.6, due to lack of proper
        introspection on that release.

        Args:
            table_name (unicode):
                The name of the table.

        Returns:
            dict:
            A dictionary mapping index names to a dictionary containing:

            ``columns`` (:py:class:`list`):
                The list of columns that the index covers.

            ``unique`` (:py:class:`bool`):
                Whether this is a unique index.
        """
        cursor = self.connection.cursor()
        qn = self.connection.ops.quote_name
        indexes = {}

        cursor.execute('PRAGMA index_list(%s);' % qn(table_name))

        for row in list(cursor.fetchall()):
            index_name = row[1]
            indexes[index_name] = {
                'unique': bool(row[2]),
                'columns': []
            }

            cursor.execute('PRAGMA index_info(%s)' % qn(index_name))

            for index_info in cursor.fetchall():
                # Column name
                indexes[index_name]['columns'].append(index_info[2])

        return indexes

    def is_column_referenced(self, reffed_table_name, reffed_col_name):
        """Return whether a column on a table is referenced by another table.

        Args:
            reffed_table_name (unicode):
                The name of the table that may be referenced.

            reffed_col_name (unicode):
                The name of the column that may be referenced.

        Returns:
            bool:
            ``True`` if this table and column are referenced by another table,
            or ``False`` if it's not referenced.
        """
        connection = self.connection
        introspection = connection.introspection
        qn = connection.ops.quote_name

        cursor = connection.cursor()

        try:
            for table_info in introspection.get_table_list(cursor):
                if isinstance(table_info, six.text_type):
                    # Django <= 1.7
                    table_name = table_info
                else:
                    # Django >= 1.8
                    table_name = table_info.name

                if table_name != reffed_table_name:
                    cursor.execute('PRAGMA foreign_key_list(%s)'
                                   % qn(table_name))

                    for row in cursor.fetchall():
                        if (reffed_table_name == row[2] and
                            reffed_col_name == row[4]):
                            return True
        finally:
            cursor.close()

        return False

    def _change_attribute(self, model, field, attr_name, new_attr_value,
                          initial=None):
        """Change an attribute on a column.

        Args:
            model (type):
                The :py:class:`~django.db.models.Model` class representing
                the table to change the column on.

            field (django.db.models.Field):
                The field representing the column to change.

            attr_name (unicode):
                The name of the attribute to change.

            new_attr_value (unicode):
                The new attribute value.

            initial (object, optional):
                The initial data to set for this attribute for existing
                rows.

        Returns:
            django_evolution.db.sql_result.SQLResult:
            The resulting SQL for rebuilding the table.
        """
        setattr(field, attr_name, new_attr_value)

        return SQLiteAlterTableSQLResult(
            evolver=self,
            model=model,
            alter_table=[
                {
                    'op': 'MODIFY COLUMN',
                    'field': field,
                    'initial': initial,
                },
            ])

"""Evolution operations backend for SQLite."""

from __future__ import unicode_literals

from django.db import models
from django.utils import six

from django_evolution.compat.db import sql_indexes_for_model
from django_evolution.compat.models import (get_remote_field,
                                            get_remote_field_model)
from django_evolution.db.common import BaseEvolutionOperations, SQLResult


TEMP_TABLE_NAME = 'TEMP_TABLE'


class EvolutionOperations(BaseEvolutionOperations):
    """Evolution operations backend for SQLite."""

    supports_constraints = False

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
        return self._rebuild_table(
            model=model,
            new_fields=[
                _field
                for _field in model._meta.local_fields
                if _field.name != field.name
            ],
            deleted_columns=[field.column])

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
            return SQLResult()

        new_fields = []

        for field in model._meta.local_fields:
            if field.name == old_field.name:
                new_fields.append(new_field)
            else:
                new_fields.append(field)

        return self._rebuild_table(
            model=model,
            new_fields=new_fields,
            renamed_columns={
                old_field.column: new_field.column,
            })

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

        return self._rebuild_table(
            model=model,
            new_fields=opts.local_fields + [field],
            new_initial={
                field.column: initial,
            },
            create_indexes=False)

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
        opts = model._meta

        return self._rebuild_table(
            model=model,
            new_fields=[
                f
                for f in opts.local_fields
                if f.db_type(connection=self.connection) is not None
            ])

    def get_indexes_for_table(self, table_name):
        """Return all known indexes on a table.

        Args:
            table_name (unicode):
                The name of the table.

        Returns:
            dict:
            A dictionary mapping index names to a dictionary containing:

            ``unique`` (:py:class:`bool`):
                Whether this is a unique index.

            ``columns`` (:py:class:`list`):
                The list of columns that the index covers.
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

        return self._rebuild_table(
            model=model,
            new_fields=model._meta.local_fields,
            new_initial={
                field.column: initial,
            },
            create_indexes=False)

    def _rebuild_table(self, model, new_fields, renamed_columns=None,
                       deleted_columns=None, new_initial=None,
                       create_indexes=True):
        """Rebuild a table with a new set of fields.

        This performs a full rebuild of a table, as per the step-by-step
        instructions recommended by SQLite. It creates a new table with the
        desired schema, copies all data from the old table, drops the old
        table, and then renames the new table over.

        It can also update the newly-populated rows in the new table with
        new initial data, if needed by a new column.

        Args:
            model (type):
                The model (subclass of :py:class:`django.db.models.Model`
                representing the table to rebuild.

            new_fields (list of django.db.models.Field):
                The list of fields to include in the new table. This may
                be different from the old table's list of fields, allowing
                new fields to be added, old fields to be removed, or field
                definitions to change.

            renamed_columns (dict, optional):
                A dictionary mapping old column names to their new column
                names.

            deleted_columns (list of unicode, optional):
                A list of any columns being deleted.

            new_initial (dict, optional):
                A mapping of columns to any new initial values to set in the
                table.

            create_indexes (bool, optional):
                Whether to recreate any indexes for the table.

        Returns:
            django_evolution.db.sql_result.SQLResult:
            The resulting SQL for rebuilding the table.
        """
        connection = self.connection
        qn = connection.ops.quote_name
        table_name = model._meta.db_table

        # Remove any Generic Fields.
        old_fields = [
            field
            for field in model._meta.local_fields
            if field.db_type(connection=connection) is not None
        ]

        new_fields = [
            field
            for field in new_fields
            if field.db_type(connection=connection) is not None
        ]

        old_column_names = [
            field.column
            for field in old_fields
        ]

        copy_old_column_names = old_column_names

        if renamed_columns:
            copy_new_column_names = (
                renamed_columns.get(col_name, col_name)
                for col_name in old_column_names
            )
        else:
            copy_new_column_names = old_column_names

        if deleted_columns:
            deleted_columns = set(deleted_columns)

            copy_old_column_names = [
                column
                for column in copy_old_column_names
                if column not in deleted_columns
            ]

            copy_new_column_names = [
                column
                for column in copy_new_column_names
                if column not in deleted_columns
            ]

        sql_result = SQLResult()

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

        for field in new_fields:
            if not isinstance(field, models.ManyToManyField):
                column_name = qn(field.column)
                column_type = field.db_type(connection=self.connection)
                params = [column_name, column_type]

                # Always use null if this is a temporary table. It may be
                # used to create a new field (which will be null while data is
                # copied across from the old table).
                if field.null:
                    params.append('NULL')
                else:
                    params.append('NOT NULL')

                if field.unique:
                    params.append('UNIQUE')

                if field.primary_key:
                    params.append('PRIMARY KEY')

                if isinstance(field, models.ForeignKey):
                    remote_field = get_remote_field(field)
                    remote_field_model = get_remote_field_model(remote_field)

                    params.append(
                        'REFERENCES %s (%s) DEFERRABLE INITIALLY DEFERRED'
                        % (qn(remote_field_model._meta.db_table),
                           qn(remote_field_model._meta.get_field(
                               remote_field.field_name).column)))

                columns_sql.append(' '.join(params))

        sql_result.add('CREATE TABLE %s (%s);' % (qn(TEMP_TABLE_NAME),
                                                  ', '.join(columns_sql)))

        # Step 2: Copy over any data from the old table into the new one.
        sql_result.add(
            'INSERT INTO %s (%s) SELECT %s FROM %s;'
            % (
                qn(TEMP_TABLE_NAME),
                ', '.join(
                    qn(column)
                    for column in copy_new_column_names
                ),
                ', '.join(
                    qn(column)
                    for column in copy_old_column_names
                ),
                qn(table_name),
            ))

        # Note that initial will only be None if null=True. Otherwise, it
        # will be set to a user-defined callable or the default
        # AddFieldInitialCallback, which will raise an exception in common
        # code before we get too much further.
        if new_initial:
            initial_column_sql = []
            initial_values = []

            for column, initial in six.iteritems(new_initial):
                if initial is not None:
                    if callable(initial):
                        value_sql = initial()
                    else:
                        initial_values.append(initial)
                        value_sql = '%s'

                    initial_column_sql.append('%s = %s' % (qn(column),
                                                           value_sql))

            if initial_column_sql:
                update_sql = 'UPDATE %s SET %s;' % (
                    qn(TEMP_TABLE_NAME),
                    ', '.join(initial_column_sql)
                )

                sql_result.add((update_sql, tuple(initial_values)))

        # Step 3: Drop the old table, making room for us to recreate the
        #         new schema table in its place.
        sql_result.add(self.delete_table(table_name))

        # Step 4: Move over the temp table to the destination table name.
        sql_result.add(self.get_rename_table_sql(
            model, TEMP_TABLE_NAME, table_name))

        # Step 5: Restore any indexes.
        if create_indexes:
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

            sql_result.add(sql_indexes_for_model(connection, _Model))

        return sql_result

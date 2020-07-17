from __future__ import unicode_literals

import copy
import logging

import django
from django.db import connection as default_connection, models
from django.utils import six

from django_evolution import support
from django_evolution.compat.db import (create_index_name,
                                        create_index_together_name,
                                        sql_add_constraints,
                                        sql_create_for_many_to_many_field,
                                        sql_delete_constraints,
                                        sql_delete_index,
                                        sql_indexes_for_field,
                                        sql_indexes_for_fields,
                                        truncate_name)
from django_evolution.compat.models import (get_remote_field,
                                            get_remote_field_model)
from django_evolution.db.sql_result import AlterTableSQLResult, SQLResult
from django_evolution.errors import EvolutionNotImplementedError


class BaseEvolutionOperations(object):
    supported_change_attrs = (
        'null', 'max_length', 'db_column', 'db_index', 'db_table', 'unique',
    )

    # Build the list of ChangeMeta attributes that databases support by
    # default.
    supported_change_meta = {
        'indexes': support.supports_indexes,
        'index_together': support.supports_index_together,
        'unique_together': True,
    }

    supports_constraints = True

    mergeable_ops = (
        'add_column', 'change_column', 'delete_column', 'change_meta'
    )

    alter_table_sql_result_cls = AlterTableSQLResult

    def __init__(self, database_state, connection=default_connection):
        """Initialize the evolution operations.

        Args:
            database_state (django_evolution.db.state.DatabaseState):
                The database state to track information through.

            connection (object):
                The database connection.
        """
        self.database_state = database_state
        self.connection = connection

    def generate_table_ops_sql(self, mutator, ops):
        """Generates SQL for a sequence of mutation operations.

        This will process each operation one-by-one, generating default SQL,
        using generate_table_op_sql().
        """
        sql_results = []
        prev_sql_result = None
        prev_op = None

        for op in ops:
            sql_result = self.generate_table_op_sql(mutator, op,
                                                    prev_sql_result, prev_op)

            if sql_result is not prev_sql_result:
                sql_results.append(sql_result)
                prev_sql_result = sql_result

            prev_op = op

        sql = []

        for sql_result in sql_results:
            sql.extend(sql_result.to_sql())

        return sql

    def generate_table_op_sql(self, mutator, op, prev_sql_result, prev_op):
        """Generates SQL for a single mutation operation.

        This will call different SQL-generating functions provided by the
        class, depending on the details of the operation.

        If two adjacent operations can be merged together (meaning that
        they can be turned into one ALTER TABLE statement), they'll be placed
        in the same AlterTableSQLResult.
        """
        model = mutator.create_model()

        op_type = op['type']
        mutation = op['mutation']

        if prev_op and self._are_ops_mergeable(prev_op, op):
            sql_result = prev_sql_result
        else:
            sql_result = self.alter_table_sql_result_cls(self, model)

        if op_type == 'add_column':
            field = op['field']
            sql_result.add(self.add_column(model, field, op['initial']))
        elif op_type == 'change_column':
            sql_result.add(self.change_column_attrs(model, mutation,
                                                    op['field'].name,
                                                    op['new_attrs']))
        elif op_type == 'delete_column':
            sql_result.add(self.delete_column(model, op['field']))
        elif op_type == 'change_meta':
            evolve_func = getattr(self, 'change_meta_%s' % op['prop_name'])
            sql_result.add(evolve_func(model, op['old_value'],
                                       op['new_value']))
        elif op_type == 'sql':
            sql_result.add(op['sql'])
        else:
            raise EvolutionNotImplementedError(
                'Unknown mutation operation "%s"' % op_type)

        mutator.finish_op(op)

        return sql_result

    def quote_sql_param(self, param):
        "Add protective quoting around an SQL string parameter"
        if isinstance(param, six.string_types):
            return "'%s'" % six.text_type(param).replace("'", r"\'")
        else:
            return param

    def rename_column(self, model, old_field, new_field):
        """Renames the specified column.

        This must be implemented by subclasses. It must return an SQLResult
        or AlterTableSQLResult representing the SQL needed to rename the
        column.
        """
        raise NotImplementedError

    def get_rename_table_sql(self, model, old_db_tablename, db_tablename):
        qn = self.connection.ops.quote_name

        # We want to define an explicit ALTER TABLE here, instead of setting
        # alter_table in AlterTableSQLResult, so that we can be explicit about
        # the old and new table names.
        return SQLResult(['ALTER TABLE %s RENAME TO %s;'
                          % (qn(old_db_tablename), qn(db_tablename))])

    def rename_table(self, model, old_db_tablename, db_tablename):
        sql_result = SQLResult()

        if old_db_tablename == db_tablename:
            # No Operation
            return sql_result

        max_name_length = self.connection.ops.max_name_length()

        refs = {}
        models = []

        for field in model._meta.local_many_to_many:
            remote_field = get_remote_field(field)

            if (remote_field and
                remote_field.through and
                remote_field.through._meta.db_table == old_db_tablename):

                through = remote_field.through

                for m2m_field in through._meta.local_fields:
                    remote_m2m_field = get_remote_field(m2m_field)

                    if remote_m2m_field:
                        remote_m2m_field_model = get_remote_field_model(
                            remote_m2m_field)

                        if remote_m2m_field_model == model:
                            models.append(remote_m2m_field_model)
                            refs.setdefault(remote_m2m_field_model, []).append(
                                (through, m2m_field))

        remove_refs = refs.copy()

        if self.supports_constraints:
            for relto in models:
                sql_result.add_pre_sql(sql_delete_constraints(
                    self.connection, relto, remove_refs))

        sql_result.add(self.get_rename_table_sql(
            model, old_db_tablename, db_tablename))

        for relto in models:
            for rel_class, f in refs[relto]:
                if rel_class._meta.db_table == old_db_tablename:
                    rel_class._meta.db_table = db_tablename

                rel_class._meta.db_table = \
                    truncate_name(rel_class._meta.db_table,
                                  max_name_length)

            if self.supports_constraints:
                sql_result.add_post_sql(sql_add_constraints(
                    self.connection, relto, refs))

        return sql_result

    def delete_column(self, model, f):
        return self.alter_table_sql_result_cls(
            self,
            model,
            [
                {
                    'op': 'DROP COLUMN',
                    'column': f.column,
                    'params': ['CASCADE']
                },
            ],
        )

    def delete_table(self, table_name):
        qn = self.connection.ops.quote_name
        return SQLResult(['DROP TABLE %s;' % qn(table_name)])

    def add_m2m_table(self, model, field):
        """Return SQL statements for creating a ManyToManyField's table.

        Args:
            model (django.db.models.Model):
                The database model owning the field.

            field (django.db.models.ManyToManyField):
                The field owning the table.

        Returns:
            list:
            The list of SQL statements for creating the table.
        """
        return sql_create_for_many_to_many_field(self.connection, model, field)

    def add_column(self, model, f, initial):
        qn = self.connection.ops.quote_name
        sql_result = self.alter_table_sql_result_cls(self, model)
        table_name = model._meta.db_table

        remote_field = get_remote_field(f)

        if remote_field:
            # it is a foreign key field
            # NOT NULL REFERENCES "django_evolution_addbasemodel"
            # ("id") DEFERRABLE INITIALLY DEFERRED

            # ALTER TABLE <tablename> ADD COLUMN <column name> NULL
            # REFERENCES <tablename1> ("<colname>") DEFERRABLE INITIALLY
            # DEFERRED
            related_model = get_remote_field_model(remote_field)
            related_table = related_model._meta.db_table
            related_pk_col = related_model._meta.pk.name
            constraints = ['%sNULL' % (not f.null and 'NOT ' or '')]

            if f.unique or f.primary_key:
                constraints.append('UNIQUE')

            sql_result.add_alter_table([
                {
                    'op': 'ADD COLUMN',
                    'column': f.column,
                    'db_type': f.db_type(connection=self.connection),
                    'params': constraints + [
                        'REFERENCES',
                        qn(related_table),
                        '(%s)' % qn(related_pk_col),
                        self.connection.ops.deferrable_sql(),
                    ]
                }
            ])
        else:
            null_constraints = '%sNULL' % (not f.null and 'NOT ' or '')

            if f.unique or f.primary_key:
                unique_constraints = 'UNIQUE'
            else:
                unique_constraints = ''

            # At this point, initial can only be None if null=True,
            # otherwise it is a user callable or the default
            # AddFieldInitialCallback which will shortly raise an exception.
            if initial is not None:
                if callable(initial):
                    sql_result.add_alter_table([
                        {
                            'op': 'ADD COLUMN',
                            'column': f.column,
                            'db_type': f.db_type(connection=self.connection),
                            'params': [unique_constraints],
                        }
                    ])

                    sql_result.add_sql([
                        'UPDATE %s SET %s = %s WHERE %s IS NULL;'
                        % (qn(table_name), qn(f.column),
                           initial(), qn(f.column))
                    ])

                    if not f.null:
                        # Only put this sql statement if the column cannot
                        # be null.
                        sql_result.add_sql(
                            self.set_field_null(model, f, f.null))
                else:
                    sql_result.add_alter_table([
                        {
                            'op': 'ADD COLUMN',
                            'column': f.column,
                            'db_type': f.db_type(connection=self.connection),
                            'params': [
                                null_constraints,
                                unique_constraints,
                                'DEFAULT',
                                '%s',
                            ],
                            'sql_params': [initial]
                        }
                    ])

                    # Django doesn't generate default columns, so now that
                    # we've added one to get default values for existing
                    # tables, drop that default.
                    sql_result.add_post_sql([
                        'ALTER TABLE %s ALTER COLUMN %s DROP DEFAULT;'
                        % (qn(table_name), qn(f.column))
                    ])
            else:
                sql_result.add_alter_table([
                    {
                        'op': 'ADD COLUMN',
                        'column': f.column,
                        'db_type': f.db_type(connection=self.connection),
                        'params': [null_constraints, unique_constraints],
                    }
                ])

        if f.unique or f.primary_key:
            self.database_state.add_index(
                table_name=table_name,
                index_name=self.get_new_constraint_name(table_name, f.column),
                columns=[f.column],
                unique=True)

        sql_result.add(self.create_index(model, f))

        return sql_result

    def set_field_null(self, model, field, null):
        if null:
            attr = 'DROP NOT NULL'
        else:
            attr = 'SET NOT NULL'

        return self.alter_table_sql_result_cls(
            self,
            model,
            [
                {
                    'op': 'ALTER COLUMN',
                    'column': field.column,
                    'params': [attr],
                },
            ]
        )

    def create_index(self, model, field):
        """Returns the SQL for creating an index for a single field.

        The index will be recorded in the database signature for future
        operations within the transaction, and the appropriate SQL for
        creating the index will be returned.

        This is not intended to be overridden.
        """
        table_name = model._meta.db_table
        column = field.column
        index_state = self.database_state.find_index(
            table_name=table_name,
            columns=[column])

        if index_state:
            return []

        self.database_state.add_index(
            table_name=table_name,
            index_name=create_index_name(self.connection,
                                         table_name,
                                         field_names=[field.name],
                                         col_names=[column]),
            columns=[column])

        return SQLResult(sql_indexes_for_field(self.connection, model, field))

    def create_unique_index(self, model, index_name, fields):
        qn = self.connection.ops.quote_name
        table_name = model._meta.db_table

        self.database_state.add_index(
            table_name=table_name,
            index_name=index_name,
            columns=self.get_column_names_for_fields(fields),
            unique=True)

        return SQLResult([
            'CREATE UNIQUE INDEX %s ON %s (%s);'
            % (qn(index_name), qn(table_name),
               ', '.join([qn(field.column) for field in fields])),
        ])

    def drop_index(self, model, field):
        """Returns the SQL for dropping an index for a single field.

        The index matching the field's column will be looked up and,
        if found, the SQL for dropping it will be returned.

        If the index was not found on the database or in the database
        signature, this won't return any SQL statements.

        This is not intended to be overridden. Instead, subclasses should
        override `get_drop_index_sql`.
        """
        index_state = self.database_state.find_index(
            table_name=model._meta.db_table,
            columns=[field.column])

        if index_state:
            return self.drop_index_by_name(model, index_state.name)

        return []

    def drop_index_by_name(self, model, index_name):
        """Returns the SQL to drop an index, given an index name.

        The index will be removed fom the database signature, and
        the appropriate SQL for dropping the index will be returned.

        This is not intended to be overridden. Instead, subclasses should
        override `get_drop_index_sql`.
        """
        self.database_state.remove_index(table_name=model._meta.db_table,
                                         index_name=index_name)

        return self.get_drop_index_sql(model, index_name)

    def get_drop_index_sql(self, model, index_name):
        """Returns the database-specific SQL to drop an index.

        This can be overridden by subclasses if they use a syntax
        other than "DROP INDEX <name>;"
        """
        return SQLResult(sql_delete_index(connection=self.connection,
                                          model=model,
                                          index_name=index_name))

    def get_new_index_name(self, model, fields, unique=False):
        """Return a newly generated index name.

        This returns a unique index name for any indexes created by
        django-evolution, based on how Django would compute the index.

        Args:
            model (django.db.models.Model):
                The database model for the index.

            fields (list of django.db.models.Field):
                The list of fields for the index.

            unique (bool, optional):
                Whether this index is unique.

        Returns:
            str:
            The generated name for the index.
        """
        return create_index_name(
            self.connection,
            table_name=model._meta.db_table,
            field_names=[f.name for f in fields],
            col_names=[f.column for f in fields],
            unique=unique)

    def get_new_constraint_name(self, table_name, column):
        """Return a newly-generated constraint name.

        Args:
            table_name (unicode):
                The name of the table.

            column (unicode):
                The name of the column.

        Returns:
            unicode:
            The new constraint name.
        """
        return truncate_name('%s_%s_key' % (table_name, column),
                             self.connection.ops.max_name_length())

    def get_default_index_name(self, table_name, field):
        """Return a default index name for the database.

        This will return an index name for the given field that matches what
        the database or Django database backend would automatically generate
        when marking a field as indexed or unique.

        This can be overridden by subclasses if the database or Django
        database backend provides different values.

        Args:
            table_name (str):
                The name of the table for the index.

            field (django.db.models.Field):
                The field for the index.

        Returns:
            str:
            The name of the index.
        """
        assert field.unique or field.db_index

        if field.unique:
            return truncate_name(field.column,
                                 self.connection.ops.max_name_length())
        elif field.db_index:
            return create_index_name(self.connection, table_name,
                                     field_names=[field.name],
                                     col_names=[field.column])
        else:
            # This won't be reached, due to the assert above.
            raise NotImplementedError

    def get_default_index_together_name(self, table_name, fields):
        """Returns a default index name for an index_together.

        This will return an index name for the given field that matches what
        Django uses for index_together fields.

        Args:
            table_name (str):
                The name of the table for the index.

            fields (list of django.db.models.Field):
                The fields for the index.

        Returns:
            str:
            The name of the index.
        """
        return create_index_together_name(
            self.connection,
            table_name,
            [field.name for field in fields])

    def change_column_attrs(self, model, mutation, field_name, new_attrs):
        """Returns the SQL for changing one or more column attributes.

        This will generate all the statements needed for changing a set
        of attributes for a column.

        The resulting AlterTableSQLResult contains all the SQL needed
        to apply these attributes.
        """
        field = model._meta.get_field(field_name)
        attrs_sql_result = self.alter_table_sql_result_cls(self, model)

        new_attrs = sorted(six.iteritems(new_attrs),
                           key=lambda pair: pair[0])

        for attr_name, attr_info in new_attrs:
            method_name = 'change_column_attr_%s' % attr_name
            evolve_func = getattr(self, method_name)

            try:
                sql_result = evolve_func(model, mutation, field,
                                         attr_info['old_value'],
                                         attr_info['new_value'])
                assert not sql_result or isinstance(sql_result, SQLResult)
            except Exception as e:
                logging.critical(
                    'Error running database evolver function %s: %s',
                    method_name, e,
                    exc_info=1)
                raise

            attrs_sql_result.add(sql_result)

        return attrs_sql_result

    def change_column_attr_null(self, model, mutation, field, old_value,
                                new_value):
        """Returns the SQL for changing a column's NULL/NOT NULL attribute."""
        qn = self.connection.ops.quote_name
        initial = mutation.initial
        opts = model._meta
        pre_sql = []

        if not new_value and initial is not None:
            sql_prefix = (
                'UPDATE %(table_name)s SET %(column_name)s = %%s'
                ' WHERE %(column_name)s IS NULL;'
                % {
                    'table_name': qn(opts.db_table),
                    'column_name': qn(field.column),
                }
            )

            if callable(initial):
                update_sql = sql_prefix % initial()
            else:
                update_sql = (sql_prefix, (initial,))

            pre_sql.append(update_sql)

        sql_result = self.set_field_null(model, field, new_value)
        sql_result.add_pre_sql(pre_sql)

        return sql_result

    def change_column_attr_max_length(self, model, mutation, field, old_value,
                                      new_value):
        """Returns the SQL for changing a column's max length."""
        field.max_length = new_value

        qn = self.connection.ops.quote_name
        column = field.column
        db_type = field.db_type(connection=self.connection)

        return self.alter_table_sql_result_cls(
            self,
            model,
            [
                {
                    'op': 'ALTER COLUMN',
                    'column': column,
                    'params': [
                        'TYPE %s USING CAST(%s as %s)'
                        % (db_type, qn(column), db_type),
                    ],
                },
            ]
        )

    def change_column_attr_db_column(self, model, mutation, field, old_value,
                                     new_value):
        """Returns the SQL for changing a column's name."""
        new_field = copy.copy(field)
        new_field.column = new_value

        return self.rename_column(model, field, new_field)

    def change_column_attr_db_table(self, model, mutation, field, old_value,
                                    new_value):
        """Returns the SQL for changing the table for a ManyToManyField."""
        return self.rename_table(model, old_value, new_value)

    def change_column_attr_db_index(self, model, mutation, field, old_value,
                                    new_value):
        """Returns the SQL for creating/dropping indexes for a column."""
        field.db_index = new_value

        if new_value:
            return self.create_index(model, field)
        else:
            return self.drop_index(model, field)

    def change_column_attr_unique(self, model, mutation, field, old_value,
                                  new_value):
        """Returns the SQL to change a field's unique flag.

        Changing the unique flag for a given column will affect indexes.
        If setting unique to True, an index will be created in the
        database signature for future operations within the transaction.
        If False, the index will be dropped from the database signature.

        The SQL needed to change the column will be returned.

        This is not intended to be overridden. Instead, subclasses should
        override `get_change_unique_sql`.
        """
        table_name = model._meta.db_table
        constraint_name = None

        if new_value:
            constraint_name = self.get_new_index_name(model, [field],
                                                      unique=True)
            self.database_state.add_index(
                table_name=table_name,
                index_name=constraint_name,
                columns=[field.column],
                unique=True)
        else:
            index_state = self.database_state.find_index(
                table_name=table_name,
                columns=[field.column],
                unique=True)

            assert index_state
            constraint_name = index_state.name
            self.database_state.remove_index(table_name=table_name,
                                             index_name=constraint_name,
                                             unique=True)

        return self.get_change_unique_sql(model, field, new_value,
                                          constraint_name, mutation.initial)

    def get_change_unique_sql(self, model, field, new_unique_value,
                              constraint_name, initial):
        """Returns the database-specific SQL to change a column's unique flag.

        This can be overridden by subclasses if they use a different syntax.
        """
        qn = self.connection.ops.quote_name

        if new_unique_value:
            alter_table_item = {
                'sql': 'ADD CONSTRAINT %s UNIQUE(%s)'
                       % (qn(constraint_name), qn(field.column))
            }
        else:
            alter_table_item = {
                'sql': 'DROP CONSTRAINT %s' % qn(constraint_name)
            }

        return self.alter_table_sql_result_cls(self, model, [alter_table_item])

    def get_drop_unique_constraint_sql(self, model, index_name):
        return self.get_drop_index_sql(model, index_name)

    def change_meta_unique_together(self, model, old_unique_together,
                                    new_unique_together):
        """Change the unique_together constraints of a table.

        Args:
            model (django.db.models.Model):
                The model being changed.

            old_unique_together (list):
                The old value for ``unique_together``.

            new_unique_together (list):
                The new value for ``unique_together``.

        Returns:
            django_evolution.sql_result.SQLResult:
            The SQL statements for changing the ``unique_together``
            constraints.
        """
        sql_result = SQLResult()
        table_name = model._meta.db_table

        old_unique_together = set(old_unique_together)
        new_unique_together = set(new_unique_together)

        to_remove = old_unique_together.difference(new_unique_together)

        for field_names in to_remove:
            fields = self.get_fields_for_names(model, field_names)
            index_state = self.database_state.find_index(
                table_name=table_name,
                columns=self.get_column_names_for_fields(fields),
                unique=True)

            if index_state:
                index_name = index_state.name

                self.database_state.remove_index(table_name=table_name,
                                                 index_name=index_name,
                                                 unique=True)
                sql_result.add_sql(
                    self.get_drop_unique_constraint_sql(model, index_name))

        for field_names in new_unique_together:
            fields = self.get_fields_for_names(model, field_names)
            index_state = self.database_state.find_index(
                table_name=table_name,
                columns=self.get_column_names_for_fields(fields),
                unique=True)

            if not index_state:
                # This doesn't exist in the database, so we want to add it.
                index_name = self.get_new_index_name(model, fields,
                                                     unique=True)
                sql_result.add_sql(
                    self.create_unique_index(model, index_name, fields))

        return sql_result

    def change_meta_index_together(self, model, old_index_together,
                                   new_index_together):
        """Change the index_together indexes of a table.

        Args:
            model (django.db.models.Model):
                The model being changed.

            old_index_together (list):
                The old value for ``index_together``.

            new_index_together (list):
                The new value for ``index_together``.

        Returns:
            django_evolution.sql_result.SQLResult:
            The SQL statements for changing the ``index_together`` indexes.
        """
        sql_result = SQLResult()
        table_name = model._meta.db_table

        old_index_together = set(old_index_together or [])
        new_index_together = set(new_index_together)

        to_remove = old_index_together.difference(new_index_together)

        for field_names in to_remove:
            fields = self.get_fields_for_names(model, field_names)
            index_state = self.database_state.find_index(
                table_name=table_name,
                columns=self.get_column_names_for_fields(fields))

            if index_state:
                sql_result.add(self.drop_index_by_name(model,
                                                       index_state.name))

        for field_names in new_index_together:
            fields = self.get_fields_for_names(model, field_names)
            columns = self.get_column_names_for_fields(fields)
            index_state = self.database_state.find_index(table_name=table_name,
                                                         columns=columns)

            if not index_state:
                # This doesn't exist in the database, so we want to add it.
                index_name = self.get_default_index_together_name(table_name,
                                                                  fields)
                self.database_state.add_index(table_name=table_name,
                                              index_name=index_name,
                                              columns=columns)
                sql_result.add(sql_indexes_for_fields(
                    self.connection, model, fields, index_together=True))

        return sql_result

    def change_meta_indexes(self, model, old_indexes, new_indexes):
        """Change the indexes of a table defined in a model's indexes list.

        This will apply a set of indexes serialized from a
        :py:attr:`Meta.indexes <django.db.models.options.Options.indexes>`
        to the database. The serialized values are those passed to
        :py:class:`~django_evolution.mutations.ChangeMeta`, in the form of::

            [
                {
                    'name': 'optional-index-name',
                    'fields': ['field1', '-field2_sorted_desc'],
                },
                ...
            ]

        Args:
            model (django.db.models.Model):
                The model being changed.

            old_indexes (list):
                The old serialized value for the indexes.

            new_indexes (list):
                The new serialized value for the indexes.

        Returns:
            django_evolution.sql_result.SQLResult:
            The SQL statements for changing the indexes.
        """
        # The mutation should have failed before getting here on older
        # versions of Django.
        assert django.VERSION >= (1, 11)

        if not old_indexes:
            old_indexes = []

        # We're working with dictionaries and lists, which we can't just pass
        # into set() like we would for the other methods. We need to calculate
        # an explicit, ordered list of indexes, so to do this, we're going to
        # build a set of tuples representing the old values and the new
        # values, and then calculate an ordered list of indexes to remove and
        # to add based on values found in those sets.
        def _make_index_tuple(index_info):
            return (index_info.get('name'), tuple(index_info['fields']))

        old_indexes_set = set(
            _make_index_tuple(index_info)
            for index_info in old_indexes
        )

        new_indexes_set = set(
            _make_index_tuple(index_info)
            for index_info in new_indexes
        )

        to_remove = [
            index_info
            for index_info in old_indexes
            if _make_index_tuple(index_info) not in new_indexes_set
        ]

        to_add = [
            index_info
            for index_info in new_indexes
            if _make_index_tuple(index_info) not in old_indexes_set
        ]

        sql_result = SQLResult()
        table_name = model._meta.db_table

        with self.connection.schema_editor(collect_sql=True) as schema_editor:
            for index_info in to_remove:
                index_field_names = index_info['fields']
                index_name = index_info.get('name')

                if index_name:
                    index_state = self.database_state.get_index(
                        table_name=table_name,
                        index_name=index_name)
                else:
                    # No explicit index name was given, so see if we can find
                    # one that matches in the database.
                    fields = self.get_fields_for_names(
                        model,
                        index_field_names,
                        allow_sort_prefixes=True)
                    index_state = self.database_state.find_index(
                        table_name=table_name,
                        columns=self.get_column_names_for_fields(fields))

                if index_state:
                    # We found a suitable index name, and a matching index
                    # entry in the database. Remove it.
                    index = models.Index(fields=list(index_field_names),
                                         name=index_state.name)
                    sql_result.add('%s;' % index.remove_sql(model,
                                                            schema_editor))

            for index_info in to_add:
                index_field_names = index_info['fields']
                index_name = index_info.get('name')
                fields = self.get_fields_for_names(model, index_field_names,
                                                   allow_sort_prefixes=True)

                if index_name:
                    index_state = self.database_state.get_index(
                        table_name=table_name,
                        index_name=index_name)
                else:
                    # No explicit index name was given, so see if we can find
                    # one that matches in the database.
                    index_state = self.database_state.find_index(
                        table_name=table_name,
                        columns=self.get_column_names_for_fields(fields))

                    if index_state:
                        index_name = index_state.name

                if not index_name or not index_state:
                    # This is a new index not found in the database. We can
                    # record it and proceed.
                    index = models.Index(fields=list(index_field_names),
                                         name=index_name)

                    if not index_name:
                        index.set_name_with_model(model)

                    self.database_state.add_index(
                        table_name=table_name,
                        index_name=index.name,
                        columns=self.get_column_names_for_fields(fields))
                    sql_result.add('%s;' % index.create_sql(model,
                                                            schema_editor))

        return sql_result

    def get_fields_for_names(self, model, field_names,
                             allow_sort_prefixes=False):
        """Return the field instances for the given field names.

        This will go through each of the provided field names, optionally
        handling a sorting prefix (``-``, used by Django 1.11+'s
        :py:class:`~django.db.models.Index` field lists), and return the
        field instance for each.

        Args:
            model (django.db.models.Model):
                The model to fetch fields from.

            field_names (list of unicode):
                The list of field names to fetch.

            allow_sort_prefixes (bool, optional):
                Whether to allow sorting prefixes in the field names.

        Returns:
            list of django.db.models.Field:
            The resulting list of fields.
        """
        meta = model._meta
        fields = []

        for field_name in field_names:
            if allow_sort_prefixes and field_name.startswith('-'):
                field_name = field_name[1:]

            fields.append(meta.get_field(field_name))

        return fields

    def get_column_names_for_fields(self, fields):
        return [field.column for field in fields]

    def get_indexes_for_table(self, table_name):
        """Returns a dictionary of indexes from the database.

        This introspects the database to return a mapping of index names
        to index information, with the following keys:

            * columns -> list of column names
            * unique -> whether it's a unique index

        This function must be implemented by subclasses.
        """
        raise NotImplementedError

    def remove_field_constraints(self, field, opts, models, refs):
        """Return SQL for removing constraints on a field.

        Args:
            field (django.db.models.Field):
                The field the constraints will be removed from.

            opts (django.db.models.options.Options):
                The Meta class for the model.

            models (list of django.db.models.Model):
                A caller-provided list that will be populated with models
                that constraints will be removed from.

            refs (dict):
                A caller-supplied dictionary that will be populated with
                references that are removed.

                The keys are models, and the values are lists of
                tuples of many-to-many models and fields.

        Returns:
            list:
            The list of SQL statements for removing constraints on the field.
        """
        sql = []

        if self.supports_constraints and field.primary_key:
            for f in opts.local_many_to_many:
                remote_field = get_remote_field(f)

                if remote_field and remote_field.through:
                    through = remote_field.through

                    for m2m_f in through._meta.local_fields:
                        remote_m2m_f = get_remote_field(m2m_f)

                        if not remote_m2m_f:
                            continue

                        remote_m2m_f_model = \
                            get_remote_field_model(remote_m2m_f)

                        if (remote_m2m_f.field_name == field.column and
                            remote_m2m_f_model._meta.db_table ==
                                opts.db_table):
                            models.append(remote_m2m_f_model)
                            refs.setdefault(remote_m2m_f_model, []).append(
                                (through, m2m_f))

            remove_refs = refs.copy()

            for relto in models:
                sql.extend(sql_delete_constraints(self.connection, relto,
                                                  remove_refs))

        return sql

    def add_primary_key_field_constraints(self, old_field, new_field, models,
                                          refs):
        sql = []

        if self.supports_constraints and old_field.primary_key:
            for relto in models:
                for rel_class, f in refs[relto]:
                    get_remote_field(f).field_name = new_field.column

                del relto._meta._fields[old_field.name]
                relto._meta._fields[new_field.name] = new_field

                sql.extend(sql_add_constraints(self.connection, relto, refs))

        return sql

    def normalize_value(self, value):
        if isinstance(value, bool):
            return self.normalize_bool(value)

        return value

    def normalize_bool(self, value):
        if value:
            return 1
        else:
            return 0

    def _are_ops_mergeable(self, op1, op2):
        """Returns whether two operations can be merged.

        If two operation types are compatible, their operations can be
        merged together into a single AlterTableSQLResult. This checks
        to see if the operations qualify.
        """
        return (op1['type'] in self.mergeable_ops and
                op2['type'] in self.mergeable_ops)

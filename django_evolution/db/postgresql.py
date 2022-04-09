"""Evolution operations backend for Postgres."""

from __future__ import unicode_literals

import django

from django_evolution.compat.db import truncate_name
from django_evolution.db.common import BaseEvolutionOperations
from django_evolution.db.sql_result import AlterTableSQLResult
from django_evolution.utils.models import get_field_is_relation


class EvolutionOperations(BaseEvolutionOperations):
    """Evolution operations for Postgres databases."""

    default_tablespace = 'pg_default'

    change_column_type_sets_attrs = False

    #: A mapping of field types for use when altering types.
    #:
    #: Version Added:
    #:     2.2
    alter_field_type_map = {
        'bigserial': 'bigint',
        'serial': 'integer',
        'smallserial': 'smallint',
    }

    def get_change_column_type_sql(self, model, old_field, new_field):
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

        Returns:
            django_evolution.sql_result.AlterTableSQLResult:
            The SQL statements for changing the column type.
        """
        connection = self.connection
        qn = connection.ops.quote_name

        schema = self.build_column_schema(
            model=model,
            field=new_field,
            initial=new_field.default,
            skip_null_constraint=True,
            skip_primary_or_unique_constraint=True,
            skip_references=True)
        column_name = schema['name']
        table_name = model._meta.db_table

        sql_result = AlterTableSQLResult(self, model)

        old_field_type = old_field.db_type(connection=connection).lower()
        new_field_type = schema['db_type'].lower()

        was_serial = old_field_type in self.alter_field_type_map
        is_serial = new_field_type in self.alter_field_type_map

        if is_serial:
            # This is a serial field. We will need to change the type and
            # update the sequence. We will also need to choose the actual
            # type to set for the column definition.
            new_field_type = self.alter_field_type_map.get(new_field_type,
                                                           new_field_type)

        alter_type_params = ['TYPE', new_field_type] + schema['definition']

        if not self._are_column_types_compatible(old_field, new_field):
            alter_type_params += [
                'USING', '%s::%s' % (column_name, new_field_type),
            ]

        sql_result.add_alter_table([{
            'op': 'ALTER COLUMN',
            'column': column_name,
            'params': alter_type_params,
            'sql_params': schema['definition_sql_params'],
        }])

        if is_serial:
            # Reset the sequence.
            sequence_name = '%s_%s_seq' % (table_name, column_name)

            sequence_sql_result = AlterTableSQLResult(self, model)
            sequence_sql_result.add_pre_sql([
                'DROP SEQUENCE IF EXISTS %s CASCADE;' % qn(sequence_name),
                'CREATE SEQUENCE %s;' % qn(sequence_name),
            ])
            sequence_sql_result.add_alter_table([{
                'op': 'ALTER COLUMN',
                'column': column_name,
                'params': [
                    'SET',
                    'DEFAULT',
                    "nextval('%s')" % qn(sequence_name),
                ],
            }])
            sequence_sql_result.add_post_sql([
                "SELECT setval('%s', MAX(%s)) FROM %s;"
                % (qn(sequence_name),
                   qn(column_name),
                   qn(table_name)),
                'ALTER SEQUENCE %s OWNED BY %s.%s;'
                % (qn(sequence_name),
                   qn(table_name),
                   qn(column_name)),
            ])

            sql_result.add_post_sql(sequence_sql_result)
        elif was_serial:
            # Drop the old sequence, since we no longer need it.
            sequence_name = '%s_%s_seq' % (table_name, old_field.column)
            sql_result.add_post_sql([
                'DROP SEQUENCE IF EXISTS %s CASCADE;' % qn(sequence_name),
            ])

        return sql_result

    def rename_column(self, model, old_field, new_field):
        if old_field.column == new_field.column:
            # No Operation
            return []

        qn = self.connection.ops.quote_name
        max_name_length = self.connection.ops.max_name_length()

        sql_result = AlterTableSQLResult(self, model)

        pre_sql, stash = self.stash_field_ref_constraints(
            model=model,
            replaced_fields={
                old_field: new_field,
            })
        sql_result.add_pre_sql(pre_sql)

        sql_result.add_alter_table([{
            'independent': True,
            'sql': 'RENAME COLUMN %s TO %s'
                   % (truncate_name(qn(old_field.column),
                                    max_name_length),
                      truncate_name(qn(new_field.column),
                                    max_name_length)),
        }])

        sql_result.add_post_sql(self.restore_field_ref_constraints(stash))

        return sql_result

    def get_drop_unique_constraint_sql(self, model, index_name):
        qn = self.connection.ops.quote_name

        return AlterTableSQLResult(
            self,
            model,
            [{'sql': 'DROP CONSTRAINT %s' % qn(index_name)}]
        )

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
        if django.VERSION[:2] >= (1, 7):
            # On Django 1.7+, the default behavior for the index name is used.
            return super(EvolutionOperations, self).get_default_index_name(
                table_name, field)
        else:
            # On Django < 1.7, a custom form of index name is used.
            assert field.unique or field.db_index

            if field.unique:
                index_name = '%s_%s_key' % (table_name, field.column)
            elif field.db_index:
                index_name = '%s_%s' % (table_name, field.column)

            return truncate_name(index_name,
                                 self.connection.ops.max_name_length())

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
        indexes = {}

        cursor.execute(
            "SELECT i.relname as index_name, a.attname as column_name,"
            "       ix.indisunique"
            "  FROM pg_catalog.pg_class t, pg_catalog.pg_class i,"
            "       pg_catalog.pg_index ix, pg_catalog.pg_attribute a"
            " WHERE t.oid = ix.indrelid AND"
            "       i.oid = ix.indexrelid AND"
            "       a.attrelid = t.oid AND"
            "       a.attnum = ANY(ix.indkey) AND"
            "       t.relkind = 'r' AND"
            "       t.relname = %s"
            " ORDER BY i.relname, a.attnum;",
            [table_name])

        for row in cursor.fetchall():
            index_name = row[0]
            col_name = row[1]

            if index_name not in indexes:
                indexes[index_name] = {
                    'unique': row[2],
                    'columns': []
                }

            indexes[index_name]['columns'].append(col_name)

        return indexes

    def normalize_bool(self, value):
        if value:
            return True
        else:
            return False

    def change_column_attr_decimal_type(self, model, mutation, field,
                                        new_max_digits, new_decimal_places):
        """Return SQL for changing a column's max digits and decimal places.

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

        return self.alter_table_sql_result_cls(
            self,
            model,
            alter_table=[{
                'op': 'ALTER COLUMN',
                'column': field.column,
                'params': ['TYPE', field.db_type(connection=self.connection)],
            }]
        )

    def _are_column_types_compatible(self, old_field, new_field):
        """Return whether two column types are compatible.

        This is used to determine if casting needs to occur.

        If the internal types of two fields are the same, and is not an
        :py:class:`~django.contrib.postgres.fields.array.ArrayField`, then
        they are considered compatible.

        Otherwise, the Postgres column types are directly compared, iterating
        in the case of an
        :py:class:`~django.contrib.postgres.fields.array.ArrayField`.

        Version Added:
            2.2

        Args:
            old_field (django.db.models.Field):
                The old field.

            new_field (django.db.models.Field):
                The new field.

        Returns:
            bool:
            ``True`` if the column types of both fields are compatible.
            ``False`` if they are not.
        """
        old_internal_type = old_field.get_internal_type()
        new_internal_type = new_field.get_internal_type()

        if (old_internal_type == new_internal_type and
            new_internal_type != 'ArrayField'):
            return True

        return (list(self._iter_field_types(old_field)) ==
                list(self._iter_field_types(new_field)))

    def _iter_field_types(self, field):
        """Iterate through the types of fields.

        If the field is an
        :py:class:`~django.contrib.postgres.fields.array.ArrayField`, then
        this will yield the field types within.

        If this is a relation field, the relation type will be returned in
        a 1-item list.

        If this is any other kind of field, the data type will be returned
        in a 1-item list. The result may differ between versions of Django.

        Version Added:
            2.2

        Args:
            field (django.db.models.Field):
                The field to iterate through.

        Yields:
            unicode:
            Each field type.
        """
        try:
            base_field = field.base_field
        except AttributeError:
            base_field = field

        internal_type = base_field.get_internal_type()

        if internal_type == 'ArrayField':
            for field_type in self._iter_field_types(base_field):
                yield field_type
        elif get_field_is_relation(base_field):
            yield field.rel_db_type(self.connection)
        else:
            try:
                try:
                    # Django >= 1.8
                    yield self.connection.data_types[internal_type]
                except AttributeError:
                    # Django < 1.8
                    yield self.connection.creation.data_types[internal_type]
            except KeyError:
                yield field.db_type(self.connection)

"""Evolution operations backend for Postgres."""

from __future__ import unicode_literals

import django

from django_evolution.compat.db import truncate_name
from django_evolution.db.common import BaseEvolutionOperations
from django_evolution.db.sql_result import AlterTableSQLResult


class EvolutionOperations(BaseEvolutionOperations):
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

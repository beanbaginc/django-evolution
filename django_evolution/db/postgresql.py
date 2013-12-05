from django.db.backends.util import truncate_name

from django_evolution.db.common import BaseEvolutionOperations


class EvolutionOperations(BaseEvolutionOperations):
    def rename_column(self, opts, old_field, new_field):
        if old_field.column == new_field.column:
            # No Operation
            return []

        qn = self.connection.ops.quote_name
        max_name_length = self.connection.ops.max_name_length()
        sql = []
        refs = {}
        models = []

        sql.extend(self.remove_field_constraints(
            old_field, opts, models, refs))

        params = (qn(opts.db_table),
                  truncate_name(qn(old_field.column), max_name_length),
                  truncate_name(qn(new_field.column), max_name_length))
        sql.append('ALTER TABLE %s RENAME COLUMN %s TO %s;' % params)

        sql.extend(self.add_primary_key_field_constraints(
            old_field, new_field, models, refs))

        return sql

    def get_drop_unique_constraint_sql(self, model, index_name):
        qn = self.connection.ops.quote_name

        sql = [
            'ALTER TABLE %s DROP CONSTRAINT %s;'
             % (qn(model._meta.db_table), index_name),
        ]

        return sql

    def get_new_index_name(self, model, fields, unique=False):
        if unique:
            return truncate_name(
                '%s_%s_key' % (
                    model._meta.db_table,
                    '_'.join([
                        field.column for field in fields
                    ])),
                self.connection.ops.max_name_length())
        else:
            # By default, Django 1.2 will use a digest hash for the column
            # name. The PostgreSQL support, however, uses the column name
            # itself.
            return '%s_%s' % (model._meta.db_table, fields[0].column)

    def get_indexes_for_table(self, table_name):
        cursor = self.connection.cursor()
        qn = self.connection.ops.quote_name
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

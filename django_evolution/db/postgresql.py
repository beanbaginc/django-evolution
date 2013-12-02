from django.core.management import color
from django.db.backends.util import truncate_name

from common import BaseEvolutionOperations


class EvolutionOperations(BaseEvolutionOperations):
    def rename_column(self, opts, old_field, new_field):
        if old_field.column == new_field.column:
            # No Operation
            return []

        style = color.no_style()
        qn = self.connection.ops.quote_name
        max_name_length = self.connection.ops.max_name_length()
        creation = self.connection.creation
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

    def get_index_name(self, model, f):
        # By default, Django 1.2 will use a digest hash for the column name.
        # The PostgreSQL support, however, uses the column name itself.
        return '%s_%s' % (model._meta.db_table, f.column)

    def normalize_bool(self, value):
        if value:
            return True
        else:
            return False

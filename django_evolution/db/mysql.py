from django.core.management import color
from django.db.backends.util import truncate_name

from django_evolution.db.common import BaseEvolutionOperations


class EvolutionOperations(BaseEvolutionOperations):
    def delete_column(self, model, f):
        sql = []

        if f.rel:
            creation = self.connection.creation
            style = color.no_style()

            sql.extend(creation.sql_remove_table_constraints(
                f.rel.to,
                {f.rel.to: [(model, f)]},
                style))

        return sql + super(EvolutionOperations, self).delete_column(model, f)

    def rename_column(self, opts, old_field, new_field):
        if old_field.column == new_field.column:
            # No Operation
            return []

        col_type = new_field.db_type(connection=self.connection)

        if col_type is None:
            # Skip ManyToManyFields, because they're not represented as
            # database columns in this table.
            return []

        sql = []
        models = []
        refs = {}

        sql.extend(self.remove_field_constraints(
            old_field, opts, models, refs))
        sql.extend(self.get_rename_column_sql(opts, old_field, new_field))
        sql.extend(self.add_primary_key_field_constraints(
            old_field, new_field, models, refs))

        return sql

    def get_rename_column_sql(self, opts, old_field, new_field):
        qn = self.connection.ops.quote_name
        style = color.no_style()
        col_type = new_field.db_type(connection=self.connection)
        tablespace = new_field.db_tablespace or opts.db_tablespace

        # Make the definition (e.g. 'foo VARCHAR(30)') for this field.
        field_output = [
            style.SQL_FIELD(qn(new_field.column)),
            style.SQL_COLTYPE(col_type),
            style.SQL_KEYWORD('%sNULL' %
                              (not new_field.null and 'NOT ' or '')),
        ]

        if new_field.primary_key:
            field_output.append(style.SQL_KEYWORD('PRIMARY KEY'))

        if new_field.unique:
            field_output.append(style.SQL_KEYWORD('UNIQUE'))

        if (tablespace and
            self.connection.features.supports_tablespaces and
            self.connection.features.autoindexes_primary_keys and
            (new_field.unique or new_field.primary_key)):
            # We must specify the index tablespace inline, because we
            # won't be generating a CREATE INDEX statement for this field.
            field_output.append(self.connection.ops.tablespace_sql(
                tablespace, inline=True))

        if new_field.rel:
            field_output.append(
                style.SQL_KEYWORD('REFERENCES') + ' ' +
                style.SQL_TABLE(qn(new_field.rel.to._meta.db_table)) + ' (' +
                style.SQL_FIELD(qn(new_field.rel.to._meta.get_field(
                    new_field.rel.field_name).column)) + ')' +
                self.connection.ops.deferrable_sql()
            )

        pre_rename_sql = ''

        if old_field.primary_key:
            pre_rename_sql = 'DROP PRIMARY KEY, '

        return ['ALTER TABLE %s %sCHANGE COLUMN %s %s;'
                % (qn(opts.db_table),
                   pre_rename_sql,
                   qn(old_field.column),
                   ' '.join(field_output))]

    def set_field_null(self, model, f, null):
        qn = self.connection.ops.quote_name
        params = (qn(model._meta.db_table), qn(f.column),
                  f.db_type(connection=self.connection))
        if null:
            return 'ALTER TABLE %s MODIFY COLUMN %s %s DEFAULT NULL;' % params
        else:
            return 'ALTER TABLE %s MODIFY COLUMN %s %s NOT NULL;' % params

    def change_max_length(self, model, field_name, new_max_length, initial=None):
        qn = self.connection.ops.quote_name
        opts = model._meta
        f = opts.get_field(field_name)
        f.max_length = new_max_length
        params = {
            'table': qn(opts.db_table),
            'column': qn(f.column),
            'length': f.max_length,
            'type': f.db_type(connection=self.connection)
        }
        return ['UPDATE %(table)s SET %(column)s=LEFT(%(column)s,%(length)d);' % params,
                'ALTER TABLE %(table)s MODIFY COLUMN %(column)s %(type)s;' % params]

    def drop_index(self, model, f):
        qn = self.connection.ops.quote_name
        params = (qn(self.get_index_name(model, f)), qn(model._meta.db_table))
        return ['DROP INDEX %s ON %s;' % params]

    def change_unique(self, model, field_name, new_unique_value, initial=None):
        qn = self.connection.ops.quote_name
        opts = model._meta
        f = opts.get_field(field_name)
        constraint_name = '%s' % (f.column,)
        if new_unique_value:
            params = (constraint_name, qn(opts.db_table), qn(f.column),)
            return ['CREATE UNIQUE INDEX %s ON %s(%s);' % params]
        else:
            params = (constraint_name, qn(opts.db_table))
            return ['DROP INDEX %s ON %s;' % params]

    def get_rename_table_sql(self, model, old_db_tablename, db_tablename):
        qn = self.connection.ops.quote_name

        return ['RENAME TABLE %s TO %s;'
                % (qn(old_db_tablename), qn(db_tablename))]

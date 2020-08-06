"""Evolution operations backend for MySQL/MariaDB."""

from __future__ import unicode_literals

from django.core.management import color

from django_evolution.compat.db import sql_delete_constraints
from django_evolution.compat.models import (get_rel_target_field,
                                            get_remote_field,
                                            get_remote_field_model)
from django_evolution.db.common import BaseEvolutionOperations
from django_evolution.db.sql_result import AlterTableSQLResult, SQLResult


class EvolutionOperations(BaseEvolutionOperations):
    def delete_column(self, model, f):
        sql_result = AlterTableSQLResult(self, model)

        remote_field = get_remote_field(f)

        if remote_field:
            remote_field_model = get_remote_field_model(remote_field)

            sql_result.add(sql_delete_constraints(
                self.connection,
                remote_field_model,
                {remote_field_model: [(model, f)]}))

        sql_result.add_sql(
            super(EvolutionOperations, self).delete_column(model, f))

        return sql_result

    def rename_column(self, model, old_field, new_field):
        if old_field.column == new_field.column:
            # No Operation
            return []

        col_type = new_field.db_type(connection=self.connection)

        if col_type is None:
            # Skip ManyToManyFields, because they're not represented as
            # database columns in this table.
            return []

        sql_result = AlterTableSQLResult(self, model)

        pre_sql, stash = self.stash_field_ref_constraints(
            model=model,
            replaced_fields={
                old_field: new_field,
            })
        sql_result.add_pre_sql(pre_sql)

        sql_result.add_alter_table(self._get_rename_column_sql(
            opts=model._meta,
            old_field=old_field,
            new_field=new_field))

        sql_result.add_post_sql(self.restore_field_ref_constraints(stash))

        return sql_result

    def _get_rename_column_sql(self, opts, old_field, new_field):
        qn = self.connection.ops.quote_name
        style = color.no_style()
        col_type = new_field.db_type(connection=self.connection)
        tablespace = new_field.db_tablespace or opts.db_tablespace
        alter_table_item = ''

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

        new_remote_field = get_remote_field(new_field)

        if new_remote_field:
            new_remote_field_meta = \
                get_remote_field_model(new_remote_field)._meta

            field_output.append('%s %s (%s)%s' % (
                style.SQL_KEYWORD('REFERENCES'),
                style.SQL_TABLE(qn(new_remote_field_meta.db_table)),
                style.SQL_FIELD(qn(new_remote_field_meta.get_field(
                    new_remote_field.field_name).column)),
                self.connection.ops.deferrable_sql(),
            ))

        if old_field.primary_key:
            alter_table_item = 'DROP PRIMARY KEY, '

        alter_table_item += ('CHANGE COLUMN %s %s'
                             % (qn(old_field.column), ' '.join(field_output)))

        return [{'sql': alter_table_item}]

    def set_field_null(self, model, field, null):
        if null:
            null_attr = 'DEFAULT NULL'
        else:
            null_attr = 'NOT NULL'

        return AlterTableSQLResult(
            self,
            model,
            [
                {
                    'op': 'MODIFY COLUMN',
                    'column': field.column,
                    'db_type': field.db_type(connection=self.connection),
                    'params': [null_attr],
                }
            ]
        )

    def change_column_attr_max_length(self, model, mutation, field, old_value,
                                      new_value):
        qn = self.connection.ops.quote_name

        field.max_length = new_value

        db_type = field.db_type(connection=self.connection)
        params = {
            'table': qn(model._meta.db_table),
            'column': qn(field.column),
            'length': field.max_length,
            'type': db_type,
        }

        return AlterTableSQLResult(
            self,
            model,
            pre_sql=[
                'UPDATE %(table)s SET %(column)s=LEFT(%(column)s,%(length)d);'
                % params,
            ],
            alter_table=[
                {
                    'op': 'MODIFY COLUMN',
                    'column': field.column,
                    'db_type': db_type,
                },
            ]
        )

    def get_drop_index_sql(self, model, index_name):
        qn = self.connection.ops.quote_name

        return SQLResult([
            'DROP INDEX %s ON %s;'
            % (qn(index_name), qn(model._meta.db_table))
        ])

    def get_change_unique_sql(self, model, field, new_unique_value,
                              constraint_name, initial):
        qn = self.connection.ops.quote_name
        opts = model._meta
        sql = []

        if new_unique_value:
            sql.append(
                'CREATE UNIQUE INDEX %s ON %s(%s);'
                % (constraint_name, qn(opts.db_table), qn(field.column)))
        else:
            sql.append(
                'DROP INDEX %s ON %s;'
                % (constraint_name, qn(opts.db_table)))

        return SQLResult(sql)

    def get_rename_table_sql(self, model, old_db_table, new_db_table):
        """Return SQL for renaming a table.

        Args:
            model (django.db.models.Model):
                The model representing the table to rename.

            old_db_table (unicode):
                The old table name.

            new_db_table (unicode):
                The new table name.

        Returns:
            django_evolution.db.sql_result.SQLResult:
            The resulting SQL for renaming the table.
        """
        qn = self.connection.ops.quote_name

        return SQLResult([
            'RENAME TABLE %s TO %s;'
            % (qn(old_db_table), qn(new_db_table))
        ])

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
        if (hasattr(self.connection, 'schema_editor') and
            get_remote_field(field) and field.db_constraint):
            # Django >= 1.7
            target_field = get_rel_target_field(field)

            return self.connection.schema_editor()._create_index_name(
                field.model,
                [field.column],
                suffix='_fk_%s_%s' % (target_field.model._meta.db_table,
                                      target_field.column))

        return super(EvolutionOperations, self).get_default_index_name(
            table_name, field)

    def get_indexes_for_table(self, table_name):
        cursor = self.connection.cursor()
        qn = self.connection.ops.quote_name
        indexes = {}

        try:
            cursor.execute('SHOW INDEX FROM %s;' % qn(table_name))
        except Exception:
            return {}

        for row in cursor.fetchall():
            index_name = row[2]
            col_name = row[4]

            if index_name not in indexes:
                indexes[index_name] = {
                    'unique': not bool(row[1]),
                    'columns': [],
                }

            indexes[index_name]['columns'].append(col_name)

        return indexes

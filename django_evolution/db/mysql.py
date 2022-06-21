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
    """Evolution operations for MySQL and MariaDB databases."""

    _NO_DEFAULT_FIELD_TYPES = {
        # Blob types
        'blob',
        'tinyblob',
        'mediumblob',
        'longblob',

        # Text types
        'text',
        'tinytext',
        'mediumtext',
        'longtext',

        # Misc.
        'json',
    }

    def get_field_type_allows_default(self, field):
        """Return whether default values are allowed for a field.

        Version Added:
            2.2

        Args:
            field (django.db.models.Field):
                The field to check.

        Returns:
            bool:
            ``True`` if default values are allowed. ``False`` if they're not.
        """
        field_type = field.db_type(connection=self.connection)

        return (field_type is not None and
                field_type.lower() not in self._NO_DEFAULT_FIELD_TYPES)

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
        schema = self.build_column_schema(
            model=model,
            field=new_field,
            initial=new_field.default,
            skip_references=True)

        alter_table_items = []

        if old_field.primary_key:
            alter_table_items.append({
                'sql': 'DROP PRIMARY KEY',
            })

        params = [schema['db_type']]

        if new_field.null:
            params.append('NULL')
        else:
            params.append('NOT NULL')

        alter_table_items.append({
            'op': 'MODIFY',
            'column': schema['name'],
            'params': [schema['db_type']] + schema['definition'],
            'sql_params': schema['definition_sql_params'],
        })

        return AlterTableSQLResult(self, model, alter_table_items)

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
        """Rename the specified column.

        This will rename the column through ``ALTER TABLE .. CHANGE COLUMN``.

        Any constraints on the column will be stashed away before the
        ``ALTER TABLE`` and restored afterward.

        If the column has not actually changed, or it's not a real column
        (a many-to-many relation), then this will return empty statements.

        Args:
            model (type):
                The model representing the table containing the column.

            old_field (django.db.models.Field):
                The old field definition.

            new_field (django.db.models.Field):
                The new field definition.

        Returns:
            django_evolution.db.sql_result.AlterTableSQLResult or list:
            The statements for renaming the column. This may be an empty
            list if the column won't be renamed.
        """
        if old_field.column == new_field.column:
            # No Operation
            return []

        col_type = new_field.db_type(connection=self.connection)

        if col_type is None:
            # Skip ManyToManyFields, because they're not represented as
            # database columns in this table.
            return []

        qn = self.connection.ops.quote_name
        sql_result = AlterTableSQLResult(self, model)

        pre_sql, stash = self.stash_field_ref_constraints(
            model=model,
            replaced_fields={
                old_field: new_field,
            })
        sql_result.add_pre_sql(pre_sql)

        schema = self.build_column_schema(model=model,
                                          field=new_field,
                                          initial=new_field.default)

        alter_table_items = []

        if old_field.primary_key:
            alter_table_items.append('DROP PRIMARY KEY')

        alter_table_items.append(
            'CHANGE COLUMN %s %s'
            % (qn(old_field.column), ' '.join([
                qn(schema['name']),
                schema['db_type'],
            ] + schema['definition'])))

        sql_result.add_alter_table([{
            'sql': ', '.join(alter_table_items),
        }])
        sql_result.add_post_sql(self.restore_field_ref_constraints(stash))

        return sql_result

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

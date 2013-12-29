import copy

from django.core.management import color
from django.db import connection as default_connection
from django.db.backends.util import truncate_name

from django_evolution.errors import EvolutionNotImplementedError
from django_evolution.signature import (add_index_to_database_sig,
                                        remove_index_from_database_sig)
from django_evolution.support import supports_index_together


class BaseEvolutionOperations(object):
    def __init__(self, database_sig, connection=default_connection):
        self.database_sig = database_sig
        self.connection = connection

    def generate_table_ops_sql(self, mutator, ops):
        """Generates SQL for a sequence of mutation operations.

        By default, this will process each operation one-by-one, generating
        default SQL, using generate_table_op_sql().

        This can be overridden to batch operations into fewer SQL statements.
        """
        sql = []

        for op in ops:
            sql.extend(self.generate_table_op_sql(mutator, op))

        return sql

    def generate_table_op_sql(self, mutator, op):
        """Generates SQL for a single mutation operation.

        This will call different SQL-generating functions provided by the
        class, depending on the details of the operation.
        """
        sql = []
        op_type = op['type']
        mutation = op['mutation']

        model = mutator.create_model()

        if op_type == 'add_column':
            field = op['field']
            sql.extend(self.add_column(model, field, op['initial']))
            sql.extend(self.create_index(model, field))
        elif op_type == 'change_column':
            field_name = op['field'].name
            attr_name = op['attr_name']
            old_value = op['old_value']
            new_value = op['new_value']

            evolve_func = getattr(self, 'change_%s' % attr_name)

            if attr_name == 'null':
                sql.extend(evolve_func(model, field_name, new_value,
                                       mutation.initial))
            elif attr_name == 'db_table':
                sql.extend(evolve_func(model, old_value, new_value))
            else:
                sql.extend(evolve_func(model, field_name, new_value))
        elif op_type == 'delete_column':
            sql.extend(self.delete_column(model, op['field']))
        elif op_type == 'change_meta':
            evolve_func = getattr(self, 'change_%s' % op['prop_name'])
            sql.extend(evolve_func(model, op['old_value'],
                                   op['new_value']))
        elif op_type == 'sql':
            sql.extend(op['sql'])
        else:
            raise EvolutionNotImplementedError(
                'Unknown mutation operation "%s"' % op_type)

        mutator.finish_op(op)

        return sql

    def quote_sql_param(self, param):
        "Add protective quoting around an SQL string parameter"
        if isinstance(param, basestring):
            return u"'%s'" % unicode(param).replace(u"'", ur"\'")
        else:
            return param

    def get_rename_table_sql(self, model, old_db_tablename, db_tablename):
        qn = self.connection.ops.quote_name

        return ['ALTER TABLE %s RENAME TO %s;'
                % (qn(old_db_tablename), qn(db_tablename))]

    def rename_table(self, model, old_db_tablename, db_tablename):
        if old_db_tablename == db_tablename:
            # No Operation
            return []

        style = color.no_style()
        max_name_length = self.connection.ops.max_name_length()
        creation = self.connection.creation

        sql = []
        refs = {}
        models = []

        for field in model._meta.local_many_to_many:
            if (field.rel and
                field.rel.through and
                field.rel.through._meta.db_table == old_db_tablename):

                through = field.rel.through

                for m2m_field in through._meta.local_fields:
                    if m2m_field.rel and m2m_field.rel.to == model:
                        models.append(m2m_field.rel.to)
                        refs.setdefault(m2m_field.rel.to, []).append(
                            (through, m2m_field))

        remove_refs = refs.copy()

        for relto in models:
            sql.extend(creation.sql_remove_table_constraints(
                relto, remove_refs, style))

        sql.extend(self.get_rename_table_sql(
            model, old_db_tablename, db_tablename))

        for relto in models:
            for rel_class, f in refs[relto]:
                if rel_class._meta.db_table == old_db_tablename:
                    rel_class._meta.db_table = db_tablename

                rel_class._meta.db_table = \
                    truncate_name(rel_class._meta.db_table, max_name_length)

            sql.extend(creation.sql_for_pending_references(relto, style, refs))

        return sql

    def delete_column(self, model, f):
        qn = self.connection.ops.quote_name

        return ['ALTER TABLE %s DROP COLUMN %s CASCADE;'
                % (qn(model._meta.db_table), qn(f.column))]

    def delete_table(self, table_name):
        qn = self.connection.ops.quote_name
        return ['DROP TABLE %s;' % qn(table_name)]

    def add_m2m_table(self, model, f):
        style = color.no_style()
        creation = self.connection.creation

        if f.rel.through:
            references = {}
            pending_references = {}

            sql, references = creation.sql_create_model(f.rel.through, style)

            # Sort the list, in order to create consistency in the order of
            # ALTER TABLEs. This is primarily needed for unit tests.
            for refto, refs in sorted(references.iteritems(),
                                      key=lambda i: repr(i)):
                pending_references.setdefault(refto, []).extend(refs)
                sql.extend(creation.sql_for_pending_references(
                    refto, style, pending_references))

            sql.extend(creation.sql_for_pending_references(
                f.rel.through, style, pending_references))
        else:
            sql = creation.sql_for_many_to_many_field(model, f, style)

        return sql

    def add_column(self, model, f, initial):
        qn = self.connection.ops.quote_name

        if f.rel:
            # it is a foreign key field
            # NOT NULL REFERENCES "django_evolution_addbasemodel"
            # ("id") DEFERRABLE INITIALLY DEFERRED

            # ALTER TABLE <tablename> ADD COLUMN <column name> NULL
            # REFERENCES <tablename1> ("<colname>") DEFERRABLE INITIALLY
            # DEFERRED
            related_model = f.rel.to
            related_table = related_model._meta.db_table
            related_pk_col = related_model._meta.pk.name
            constraints = ['%sNULL' % (not f.null and 'NOT ' or '')]

            if f.unique or f.primary_key:
                constraints.append('UNIQUE')

            params = (qn(model._meta.db_table),
                      qn(f.column),
                      f.db_type(connection=self.connection),
                      ' '.join(constraints),
                      qn(related_table),
                      qn(related_pk_col),
                      self.connection.ops.deferrable_sql())
            output = [
                'ALTER TABLE %s ADD COLUMN %s %s %s REFERENCES %s (%s) %s;'
                % params
            ]
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
                    params = (qn(model._meta.db_table), qn(f.column),
                              f.db_type(connection=self.connection),
                              unique_constraints)
                    output = ['ALTER TABLE %s ADD COLUMN %s %s %s;' % params]
                    params = (qn(model._meta.db_table), qn(f.column),
                              initial(), qn(f.column))
                    output.append('UPDATE %s SET %s = %s WHERE %s IS NULL;'
                                  % params)
                else:
                    params = (qn(model._meta.db_table), qn(f.column),
                              f.db_type(connection=self.connection),
                              unique_constraints)
                    output = [
                        ('ALTER TABLE %s ADD COLUMN %s %s %s DEFAULT %%s;'
                         % params,
                         (initial,))
                    ]

                    # Django doesn't generate default columns, so now that
                    # we've added one to get default values for existing
                    # tables, drop that default.
                    params = (qn(model._meta.db_table), qn(f.column))
                    output.append(
                        'ALTER TABLE %s ALTER COLUMN %s DROP DEFAULT;'
                        % params)

                if not f.null:
                    # Only put this sql statement if the column cannot be null.
                    output.append(self.set_field_null(model, f, f.null))
            else:
                params = (qn(model._meta.db_table), qn(f.column),
                          f.db_type(connection=self.connection),
                          ' '.join([null_constraints, unique_constraints]))
                output = ['ALTER TABLE %s ADD COLUMN %s %s %s;' % params]

        if f.unique or f.primary_key:
            self.record_index(model, [f], use_constraint_name=True,
                              unique=True)

        return output

    def set_field_null(self, model, f, null):
        qn = self.connection.ops.quote_name
        params = (qn(model._meta.db_table), qn(f.column),)

        if null:
            return 'ALTER TABLE %s ALTER COLUMN %s DROP NOT NULL;' % params
        else:
            return 'ALTER TABLE %s ALTER COLUMN %s SET NOT NULL;' % params

    def create_index(self, model, f):
        """Returns the SQL for creating an index for a single field.

        The index will be recorded in the database signature for future
        operations within the transaction, and the appropriate SQL for
        creating the index will be returned.

        This is not intended to be overridden.
        """
        style = color.no_style()

        self.record_index(model, [f])

        return self.connection.creation.sql_indexes_for_field(model, f, style)

    def create_unique_index(self, model, index_name, fields):
        qn = self.connection.ops.quote_name

        self.record_index(model, fields)

        return [
            'CREATE UNIQUE INDEX %s ON %s (%s);'
            % (index_name, model._meta.db_table,
               ', '.join([qn(field.column) for field in fields])),
        ]

    def drop_index(self, model, f):
        """Returns the SQL for dropping an index for a single field.

        The index matching the field's column will be looked up and,
        if found, the SQL for dropping it will be returned.

        If the index was not found on the database or in the database
        signature, this won't return any SQL statements.

        This is not intended to be overridden. Instead, subclasses should
        override `get_drop_index_sql`.
        """
        index_name = self.find_index_name(model, [f.column])

        if index_name:
            return self.drop_index_by_name(model, index_name)
        else:
            return []

    def drop_index_by_name(self, model, index_name):
        """Returns the SQL to drop an index, given an index name.

        The index will be removed fom the database signature, and
        the appropriate SQL for dropping the index will be returned.

        This is not intended to be overridden. Instead, subclasses should
        override `get_drop_index_sql`.
        """
        self.remove_recorded_index(model, index_name)

        return self.get_drop_index_sql(model, index_name)

    def get_drop_index_sql(self, model, index_name):
        """Returns the database-specific SQL to drop an index.

        This can be overridden by subclasses if they use a syntax
        other than "DROP INDEX <name>;"
        """
        qn = self.connection.ops.quote_name

        return ['DROP INDEX %s;' % qn(index_name)]

    def get_new_index_name(self, model, fields, unique=False):
        """Returns a newly generated index name.

        This returns a unique index name for any indexes created by
        django-evolution. It does not need to match what Django would
        create by default.

        The default works well in most cases, but can be overridden
        for database backends that require it.
        """
        colname = self.connection.creation._digest(*[f.name for f in fields])

        return truncate_name('%s_%s' % (model._meta.db_table, colname),
                             self.connection.ops.max_name_length())

    def get_default_index_name(self, table_name, field):
        """Returns a default index name for the database.

        This will return an index name for the given field that matches what
        the database or Django database backend would automatically generate
        when marking a field as indexed or unique.

        This can be overridden by subclasses if the database or Django
        database backend provides different values.
        """
        assert field.unique or field.db_index

        if field.unique:
            index_name = field.column
        elif field.db_index:
            # This whole block of logic comes from sql_indexes_for_field
            # in django.db.backends.creation, and is designed to match
            # the logic for the past few versions of Django.
            if supports_index_together:
                # Starting in Django 1.5, the _digest is passed a raw
                # list. While this is probably a bug (digest should
                # expect a string), we still need to retain
                # compatibility. We know this behavior hasn't changed
                # as of Django 1.6.1.
                #
                # It also uses the field name, and not the column name.
                column = [field.name]
            else:
                column = field.column

            column = self.connection.creation._digest(column)
            index_name = '%s_%s' % (table_name, column)

        return truncate_name(index_name, self.connection.ops.max_name_length())

    def get_default_index_together_name(self, table_name, fields):
        """Returns a default index name for an index_together.

        This will return an index name for the given field that matches what
        Django uses for index_together fields.
        """
        index_name = '%s_%s' % (
            table_name,
            self.connection.creation._digest([f.name for f in fields]))

        return truncate_name(index_name, self.connection.ops.max_name_length())

    def change_null(self, model, field_name, new_null_attr, initial=None):
        qn = self.connection.ops.quote_name
        opts = model._meta
        f = opts.get_field(field_name)
        output = []

        if new_null_attr:
            # Setting null to True
            output.append(self.set_field_null(model, f, new_null_attr))
        else:
            if initial is not None:
                output = []

                sql_prefix = (
                    'UPDATE %(table_name)s SET %(column_name)s = %%s'
                    ' WHERE %(column_name)s IS NULL;'
                    % {
                        'table_name': qn(opts.db_table),
                        'column_name': qn(f.column),
                    }
                )

                if callable(initial):
                    sql = sql_prefix % initial()
                else:
                    sql = (sql_prefix, (initial,))

                output.append(sql)

            output.append(self.set_field_null(model, f, new_null_attr))

        return output

    def change_max_length(self, model, field_name, new_max_length,
                          initial=None):
        qn = self.connection.ops.quote_name
        opts = model._meta
        f = opts.get_field(field_name)
        f.max_length = new_max_length
        db_type = f.db_type(connection=self.connection)
        params = (qn(opts.db_table), qn(f.column),
                  db_type, qn(f.column), db_type)

        return ['ALTER TABLE %s ALTER COLUMN %s TYPE %s USING CAST(%s as %s);'
                % params]

    def change_db_column(self, model, field_name, new_db_column, initial=None):
        opts = model._meta
        old_field = opts.get_field(field_name)
        new_field = copy.copy(old_field)
        new_field.column = new_db_column

        return self.rename_column(opts, old_field, new_field)

    def change_db_table(self, model, old_db_tablename, new_db_tablename):
        return self.rename_table(model, old_db_tablename, new_db_tablename)

    def change_db_index(self, model, field_name, new_db_index, initial=None):
        f = model._meta.get_field(field_name)
        f.db_index = new_db_index

        if new_db_index:
            return self.create_index(model, f)
        else:
            return self.drop_index(model, f)

    def change_unique(self, model, field_name, new_unique_value, initial=None):
        """Returns the SQL to change a field's unique flag.

        Changing the unique flag for a given column will affect indexes.
        If setting unique to True, an index will be created in the
        database signature for future operations within the transaction.
        If False, the index will be dropped from the database signature.

        The SQL needed to change the column will be returned.

        This is not intended to be overridden. Instead, subclasses should
        override `get_change_unique_sql`.
        """
        f = model._meta.get_field(field_name)

        if new_unique_value:
            constraint_name = self.get_new_index_name(model, [f], unique=True)
            self.record_index(model, [f], index_name=constraint_name,
                              unique=True)
        else:
            constraint_name = self.find_index_name(model, [f.column],
                                                   unique=True)
            self.remove_recorded_index(model, constraint_name, unique=True)

        return self.get_change_unique_sql(model, f, new_unique_value,
                                          constraint_name, initial)

    def get_change_unique_sql(self, model, field, new_unique_value,
                              constraint_name, initial):
        """Returns the database-specific SQL to change a column's unique flag.

        This can be overridden by subclasses if they use a different syntax.
        """
        qn = self.connection.ops.quote_name
        opts = model._meta

        if new_unique_value:
            return ['ALTER TABLE %s ADD CONSTRAINT %s UNIQUE(%s);'
                    % (qn(opts.db_table), constraint_name, qn(field.column))]
        else:
            return ['ALTER TABLE %s DROP CONSTRAINT %s;'
                    % (qn(opts.db_table), constraint_name)]

    def change_unique_together(self, model, old_unique_together,
                               new_unique_together):
        """Changes the unique_together constraints of a table."""
        sql = []

        old_unique_together = set(old_unique_together)
        new_unique_together = set(new_unique_together)

        to_remove = old_unique_together.difference(new_unique_together)

        for field_names in to_remove:
            fields = self.get_fields_for_names(model, field_names)
            columns = self.get_column_names_for_fields(fields)
            index_name = self.find_index_name(model, columns, unique=True)

            if index_name:
                self.remove_recorded_index(model, index_name, unique=True)
                sql.extend(self.get_drop_unique_constraint_sql(model,
                                                               index_name))

        for field_names in new_unique_together:
            fields = self.get_fields_for_names(model, field_names)
            columns = self.get_column_names_for_fields(fields)
            index_name = self.find_index_name(model, columns, unique=True)

            if not index_name:
                # This doesn't exist in the database, so we want to add it.
                index_name = self.get_new_index_name(model, fields,
                                                     unique=True)
                sql.extend(self.create_unique_index(model, index_name, fields))

        return sql

    def get_drop_unique_constraint_sql(self, model, index_name):
        return self.get_drop_index_sql(model, index_name)

    def change_index_together(self, model, old_index_together,
                              new_index_together):
        """Changes the index_together indexes of a table."""
        sql = []
        style = color.no_style()

        old_index_together = set(old_index_together)
        new_index_together = set(new_index_together)

        to_remove = old_index_together.difference(new_index_together)

        for field_names in to_remove:
            fields = self.get_fields_for_names(model, field_names)
            columns = self.get_column_names_for_fields(fields)
            index_name = self.find_index_name(model, columns)

            if index_name:
                sql.extend(self.drop_index_by_name(model, index_name))

        for field_names in new_index_together:
            fields = self.get_fields_for_names(model, field_names)
            columns = self.get_column_names_for_fields(fields)
            index_name = self.find_index_name(model, columns)

            if not index_name:
                # This doesn't exist in the database, so we want to add it.
                self.record_index(model, fields)
                sql.extend(self.connection.creation.sql_indexes_for_fields(
                    model, fields, style))

        return sql

    def find_index_name(self, model, column_names, unique=False):
        """Finds an index in the database matching the given criteria.

        This will look in the database signature, attempting to find the
        name of an index that matches the list of columns and the
        uniqueness flag. If one is found, it will be returned. Otherwise,
        None is returned.

        This takes into account all indexes found when first beginning
        then evolution process, and those added during the evolution
        process.
        """
        if not isinstance(column_names, (list, tuple)):
            column_names = (column_names,)

        opts = model._meta
        table_name = opts.db_table

        if table_name in self.database_sig:
            indexes = self.database_sig[table_name]['indexes']

            for index_name, index_info in indexes.iteritems():
                if (index_info['columns'] == column_names and
                    index_info['unique'] == unique):
                    return index_name

        return None

    def get_fields_for_names(self, model, field_names):
        """Returns a list of fields for the given field names."""
        return [
            model._meta.get_field(field_name)
            for field_name in field_names
        ]

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
        sql = []

        if field.primary_key:
            creation = self.connection.creation
            style = color.no_style()

            for f in opts.local_many_to_many:
                if f.rel and f.rel.through:
                    through = f.rel.through

                    for m2m_f in through._meta.local_fields:
                        if (m2m_f.rel and
                            m2m_f.rel.to._meta.db_table == opts.db_table and
                            m2m_f.rel.field_name == field.column):

                            models.append(m2m_f.rel.to)
                            refs.setdefault(m2m_f.rel.to, []).append(
                                (through, m2m_f))

            remove_refs = refs.copy()
            style = color.no_style()

            for relto in models:
                sql.extend(creation.sql_remove_table_constraints(
                    relto, remove_refs, style))

        return sql

    def add_primary_key_field_constraints(self, old_field, new_field, models,
                                          refs):
        sql = []

        if old_field.primary_key:
            creation = self.connection.creation
            style = color.no_style()

            for relto in models:
                for rel_class, f in refs[relto]:
                    f.rel.field_name = new_field.column

                del relto._meta._fields[old_field.name]
                relto._meta._fields[new_field.name] = new_field

                sql.extend(creation.sql_for_pending_references(
                    relto, style, refs))

        return sql

    def record_index(self, model, fields, use_constraint_name=False,
                     index_name=None, unique=False):
        """Records an index in the database signature.

        This is a convenience to record an index in the database signature
        for future lookups. It can take an index name, or it can generate
        a constraint name if that's to be used.
        """
        if not index_name and use_constraint_name:
            index_name = truncate_name(
                '%s_%s_key' % (model._meta.db_table, fields[0].column),
                self.connection.ops.max_name_length())

        add_index_to_database_sig(self, self.database_sig, model, fields,
                                  index_name=index_name, unique=unique)

    def remove_recorded_index(self, model, index_name, unique=False):
        """Removes an index from the database signature."""
        remove_index_from_database_sig(self.database_sig, model,
                                       index_name, unique=unique)

    def normalize_value(self, value):
        if isinstance(value, bool):
            return self.normalize_bool(value)

        return value

    def normalize_bool(self, value):
        if value:
            return 1
        else:
            return 0

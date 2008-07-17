from django.core.management import color
from django.db import connection, models
import copy

class BaseEvolutionOperations(object):
    def quote_sql_param(self, param):
        "Add protective quoting around an SQL string parameter"
        if isinstance(param, basestring):
            return u"'%s'" % unicode(param).replace(u"'",ur"\'")
        else:
            return param

    def rename_table(self, old_db_tablename, db_tablename):
        if old_db_tablename == db_tablename:
            # No Operation
            return []
    
        qn = connection.ops.quote_name
        params = (qn(old_db_tablename), qn(db_tablename))
        return ['ALTER TABLE %s RENAME TO %s;' % params]
    
    def delete_column(self, model, f):
        qn = connection.ops.quote_name
        params = (qn(model._meta.db_table), qn(f.column))
    
        return ['ALTER TABLE %s DROP COLUMN %s CASCADE;' % params]

    def delete_table(self, table_name):
        qn = connection.ops.quote_name
        return ['DROP TABLE %s;' % qn(table_name)]
    
    def add_m2m_table(self, model, f):
        final_output = []
        qn = connection.ops.quote_name
        opts = model._meta
        style = color.no_style()
    
        #### Duplicated from django.core.management.sql - many_to_many_sql_for_model()
        #### If the Django core is refactored to expose single m2m table creation, 
        #### this method can be removed.
        tablespace = f.db_tablespace or opts.db_tablespace
        if tablespace and connection.features.supports_tablespaces and connection.features.autoindexes_primary_keys:
            tablespace_sql = ' ' + connection.ops.tablespace_sql(tablespace, inline=True)
        else:
            tablespace_sql = ''
        table_output = [style.SQL_KEYWORD('CREATE TABLE') + ' ' + \
            style.SQL_TABLE(qn(f.m2m_db_table())) + ' (']
        table_output.append('    %s %s %s%s,' % \
            (style.SQL_FIELD(qn('id')),
            style.SQL_COLTYPE(models.AutoField(primary_key=True).db_type()),
            style.SQL_KEYWORD('NOT NULL PRIMARY KEY'),
            tablespace_sql))
        table_output.append('    %s %s %s %s (%s)%s,' % \
            (style.SQL_FIELD(qn(f.m2m_column_name())),
            style.SQL_COLTYPE(models.ForeignKey(model).db_type()),
            style.SQL_KEYWORD('NOT NULL REFERENCES'),
            style.SQL_TABLE(qn(opts.db_table)),
            style.SQL_FIELD(qn(opts.pk.column)),
            connection.ops.deferrable_sql()))
        table_output.append('    %s %s %s %s (%s)%s,' % \
            (style.SQL_FIELD(qn(f.m2m_reverse_name())),
            style.SQL_COLTYPE(models.ForeignKey(f.rel.to).db_type()),
            style.SQL_KEYWORD('NOT NULL REFERENCES'),
            style.SQL_TABLE(qn(f.rel.to._meta.db_table)),
            style.SQL_FIELD(qn(f.rel.to._meta.pk.column)),
            connection.ops.deferrable_sql()))
        table_output.append('    %s (%s, %s)%s' % \
            (style.SQL_KEYWORD('UNIQUE'),
            style.SQL_FIELD(qn(f.m2m_column_name())),
            style.SQL_FIELD(qn(f.m2m_reverse_name())),
            tablespace_sql))
        table_output.append(')')
        if opts.db_tablespace and connection.features.supports_tablespaces:
            # f.db_tablespace is only for indices, so ignore its value here.
            table_output.append(connection.ops.tablespace_sql(opts.db_tablespace))
        table_output.append(';')
        final_output.append('\n'.join(table_output))

        # Add any extra SQL needed to support auto-incrementing PKs
        autoinc_sql = connection.ops.autoinc_sql(f.m2m_db_table(), 'id')
        if autoinc_sql:
            for stmt in autoinc_sql:
                final_output.append(stmt)

        #### END duplicated code
    
        return final_output
    
    def add_column(self, model, f, initial):
        qn = connection.ops.quote_name
    
        if f.rel:
            # it is a foreign key field
            # NOT NULL REFERENCES "django_evolution_addbasemodel" ("id") DEFERRABLE INITIALLY DEFERRED
            # ALTER TABLE <tablename> ADD COLUMN <column name> NULL REFERENCES <tablename1> ("<colname>") DEFERRABLE INITIALLY DEFERRED
            related_model = f.rel.to
            related_table = related_model._meta.db_table
            related_pk_col = related_model._meta.pk.name
            constraints = ['%sNULL' % (not f.null and 'NOT ' or '')]
            if f.unique or f.primary_key:
                constraints.append('UNIQUE')
            params = (qn(model._meta.db_table), qn(f.column), f.db_type(), ' '.join(constraints), 
                qn(related_table), qn(related_pk_col), connection.ops.deferrable_sql())
            output = ['ALTER TABLE %s ADD COLUMN %s %s %s REFERENCES %s (%s) %s;' % params]
        else:
            null_constraints = '%sNULL' % (not f.null and 'NOT ' or '')
            if f.unique or f.primary_key:
                unique_constraints = 'UNIQUE'
            else:
                unique_constraints = ''

            # At this point, initial can only be None if null=True, otherwise it is 
            # a user callable or the default AddFieldInitialCallback which will shortly raise an exception.
            if initial is not None:
                params = (qn(model._meta.db_table), qn(f.column), f.db_type(), unique_constraints)
                output = ['ALTER TABLE %s ADD COLUMN %s %s %s;' % params]
            
                if callable(initial):
                    params = (qn(model._meta.db_table), qn(f.column), initial(), qn(f.column))
                    output.append('UPDATE %s SET %s = %s WHERE %s IS NULL;' % params)
                else:
                    params = (qn(model._meta.db_table), qn(f.column), qn(f.column))
                    output.append(('UPDATE %s SET %s = %%s WHERE %s IS NULL;' % params, (initial,)))
            
                if not f.null:
                    # Only put this sql statement if the column cannot be null.
                    output.append(self.set_field_null(model, f, f.null))
            else:
                params = (qn(model._meta.db_table), qn(f.column), f.db_type(),' '.join([null_constraints, unique_constraints]))
                output = ['ALTER TABLE %s ADD COLUMN %s %s %s;' % params]
        return output

    def set_field_null(self, model, f, null):
        qn = connection.ops.quote_name
        params = (qn(model._meta.db_table), qn(f.column),)
        if null:
           return 'ALTER TABLE %s ALTER COLUMN %s DROP NOT NULL;' % params
        else:
            return 'ALTER TABLE %s ALTER COLUMN %s SET NOT NULL;' % params 
    
    def create_index(self, model, f):
        "Returns the CREATE INDEX SQL statements."
        output = []
        qn = connection.ops.quote_name
        style = color.no_style()
    
        #### Duplicated from django.core.management.sql - sql_indexes_for_model()
        #### If the Django core is refactored to expose single index creation, 
        #### this method can be removed.
        if f.db_index and not ((f.primary_key or f.unique) and connection.features.autoindexes_primary_keys):
            unique = f.unique and 'UNIQUE ' or ''
            tablespace = f.db_tablespace or model._meta.db_tablespace
            if tablespace and connection.features.supports_tablespaces:
                tablespace_sql = ' ' + connection.ops.tablespace_sql(tablespace)
            else:
                tablespace_sql = ''
            output.append(
                style.SQL_KEYWORD('CREATE %sINDEX' % unique) + ' ' + \
                style.SQL_TABLE(qn(self.get_index_name(model, f))) + ' ' + \
                style.SQL_KEYWORD('ON') + ' ' + \
                style.SQL_TABLE(qn(model._meta.db_table)) + ' ' + \
                "(%s)" % style.SQL_FIELD(qn(f.column)) + \
                "%s;" % tablespace_sql
            )
        #### END duplicated code
        return output
        
    def drop_index(self, model, f):
        qn = connection.ops.quote_name
        return ['DROP INDEX %s;' % qn(self.get_index_name(model, f))]
        
    def get_index_name(self, model, f):
        return '%s_%s' % (model._meta.db_table, f.column)
        
    def change_null(self, model, field_name, new_null_attr, initial=None):
        qn = connection.ops.quote_name
        opts = model._meta
        f = opts.get_field(field_name)
        output = []
        if new_null_attr:
            # Setting null to True
            opts = model._meta
            params = (qn(opts.db_table), qn(f.column),)
            output.append(self.set_field_null(model, f, new_null_attr))
        else:
            if initial is not None:
                output = []
                if callable(initial):
                    params = (qn(opts.db_table), qn(f.column), initial(), qn(f.column))
                    output.append('UPDATE %s SET %s = %s WHERE %s IS NULL;' % params)
                else:
                    params = (qn(opts.db_table), qn(f.column), qn(f.column))
                    output.append(('UPDATE %s SET %s = %%s WHERE %s IS NULL;' % params, (initial,)))
            output.append(self.set_field_null(model, f, new_null_attr))
            
        return output
        
    def change_max_length(self, model, field_name, new_max_length, initial=None):
        qn = connection.ops.quote_name
        opts = model._meta
        f = opts.get_field(field_name)
        f.max_length = new_max_length
        params = (qn(opts.db_table), qn(f.column), f.db_type(), qn(f.column), f.db_type())
        return ['ALTER TABLE %s ALTER COLUMN %s TYPE %s USING CAST(%s as %s);' % params]

    def change_db_column(self, model, field_name, new_db_column, initial=None):
        opts = model._meta
        old_field = opts.get_field(field_name)
        new_field = copy.copy(old_field)
        new_field.column = new_db_column
        return self.rename_column(opts, old_field, new_field)

    def change_db_table(self, old_db_tablename, new_db_tablename):
        return self.rename_table(old_db_tablename, new_db_tablename)
        
    def change_db_index(self, model, field_name, new_db_index, initial=None):
        f = model._meta.get_field(field_name)
        f.db_index = new_db_index
        if new_db_index:
            return self.create_index(model, f)
        else:
            return self.drop_index(model, f)
            
    def change_unique(self, model, field_name, new_unique_value, initial=None):
        qn = connection.ops.quote_name
        opts = model._meta
        f = opts.get_field(field_name)
        constraint_name = '%s_%s_key' % (opts.db_table, f.column,)
        if new_unique_value:
            params = (qn(opts.db_table), constraint_name, qn(f.column),)
            return ['ALTER TABLE %s ADD CONSTRAINT %s UNIQUE(%s);' % params]
        else:
            params = (qn(opts.db_table), constraint_name,)
            return ['ALTER TABLE %s DROP CONSTRAINT %s;' % params]
            

        
        
        
        
        
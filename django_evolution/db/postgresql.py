from django.core.management import color
from django.db import connection, models

def rename_column(db_table, old_col_name, new_col_name):
    if old_col_name == new_col_name:
        # No Operation
        return []
    
    qn = connection.ops.quote_name
    params = (qn(db_table), qn(old_col_name), qn(new_col_name))
    return ['ALTER TABLE %s RENAME COLUMN %s TO %s;' % params]
    
def rename_table(old_db_tablename, new_db_tablename):
    if old_db_tablename == new_db_tablename:
        # No Operation
        return []
    
    qn = connection.ops.quote_name
    params = (qn(old_db_tablename), qn(new_db_tablename))
    return ['ALTER TABLE %s RENAME TO %s;' % params]
    
def delete_column(model, f):
    qn = connection.ops.quote_name
    params = (qn(model._meta.db_table), qn(f.column))
    
    return ['ALTER TABLE %s DROP COLUMN %s CASCADE;' % params]

def delete_table(table_name):
    qn = connection.ops.quote_name
    return ['DROP TABLE %s;' % qn(table_name)]
    
def add_m2m_table(model, f):
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
    
def add_column(model, f):
    qn = connection.ops.quote_name
    
    if f.rel:
        # it is a foreign key field
        # NOT NULL REFERENCES "django_evolution_addbasemodel" ("id") DEFERRABLE INITIALLY DEFERRED
        # ALTER TABLE <tablename> ADD COLUMN <column name> NULL REFERENCES <tablename1> ("<colname>") DEFERRABLE INITIALLY DEFERRED
        related_model = f.rel.to
        related_table = related_model._meta.db_table
        related_pk_col = related_model._meta.pk.name
        constraints = ['%sNULL' % (not f.null and 'NOT ' or '')]
        if f.unique and (not f.primary_key or connection.features.allows_unique_and_pk):
            constraints.append('UNIQUE')
        params = (qn(model._meta.db_table), qn(f.column), f.db_type(), ' '.join(constraints), 
            qn(related_table), qn(related_pk_col), connection.ops.deferrable_sql())
        output = ['ALTER TABLE %s ADD COLUMN %s %s %s REFERENCES %s (%s) %s;' % params]
    else:
        constraints = ['%sNULL' % (not f.null and 'NOT ' or '')]
        if f.unique and (not f.primary_key or connection.features.allows_unique_and_pk):
            constraints.append('UNIQUE')
        params = (qn(model._meta.db_table), qn(f.column), f.db_type(),' '.join(constraints))    
        output = ['ALTER TABLE %s ADD COLUMN %s %s %s;' % params]
        
    return output
    
def create_index(model, f):
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
            style.SQL_TABLE(qn('%s_%s' % (model._meta.db_table, f.column))) + ' ' + \
            style.SQL_KEYWORD('ON') + ' ' + \
            style.SQL_TABLE(qn(model._meta.db_table)) + ' ' + \
            "(%s)" % style.SQL_FIELD(qn(f.column)) + \
            "%s;" % tablespace_sql
        )
    #### END duplicated code
    return output

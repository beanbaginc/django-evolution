
def rename_column(signature, db_table, old_col_name, new_col_name):
    params = (db_table, old_col_name, new_col_name)
    return ['ALTER TABLE %s RENAME COLUMN %s TO %s;'%params]
    
def rename_table(signature, old_db_tablename, new_db_tablename):
    params = (old_db_tablename, new_db_tablename)
    return ['ALTER TABLE %s RENAME TO %s;'%params]
    
def delete_column(signature, table_name, column_name):
    params = (table_name,column_name)
    return ['ALTER TABLE %s DROP COLUMN %s CASCADE;'%params]

def delete_table(signature, table_name):
    return ['DROP TABLE %s;'%table_name]

def add_table(app_sig, model_tablespace, field_tablespace,
              m2m_db_table, auto_field_db_type,
              m2m_column_name, m2m_reverse_name,
              fk_db_type, model_table, model_pk_column,
              rel_fk_db_type, rel_db_table, rel_pk_column):

    from django.db import connection
    final_output = []
    qn = connection.ops.quote_name
    tablespace = field_tablespace or model_tablespace
    if tablespace and connection.features.supports_tablespaces and connection.features.autoindexes_primary_keys:
        tablespace_sql = ' ' + connection.ops.tablespace_sql(tablespace, inline=True)
    else:
        tablespace_sql = ''
    table_output = ['CREATE TABLE' + ' ' + \
        qn(m2m_db_table) + ' (']
    table_output.append('    %s %s %s%s,' % \
        (qn('id'),
        auto_field_db_type,
        'NOT NULL PRIMARY KEY',
        tablespace_sql))
    table_output.append('    %s %s %s %s (%s)%s,' % \
        (qn(m2m_column_name),
        fk_db_type,
        'NOT NULL REFERENCES',
        qn(model_table),
        qn(model_pk_column),
        connection.ops.deferrable_sql()))
    table_output.append('    %s %s %s %s (%s)%s,' % \
        (qn(m2m_reverse_name),
        rel_fk_db_type,
        'NOT NULL REFERENCES',
        qn(rel_db_table),
        qn(rel_pk_column),
        connection.ops.deferrable_sql()))
    table_output.append('    %s (%s, %s)%s' % \
        ('UNIQUE',
        qn(m2m_column_name),
        qn(m2m_reverse_name),
        tablespace_sql))
    table_output.append(')')
    if model_tablespace and connection.features.supports_tablespaces:
        # field_tablespace is only for indices, so ignore its value here.
        table_output.append(connection.ops.tablespace_sql(model_tablespace))
    table_output.append(';')
    final_output.append('\n'.join(table_output))

    # Add any extra SQL needed to support auto-incrementing PKs
    autoinc_sql = connection.ops.autoinc_sql(m2m_db_table, 'id')
    if autoinc_sql:
        for stmt in autoinc_sql:
            final_output.append(stmt)
    return final_output
    
def add_column(signature, table_name, column_name, db_type):
    params = (table_name, column_name, db_type)
    return ['ALTER TABLE %s ADD COLUMN %s %s;'%params]

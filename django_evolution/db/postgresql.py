
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
    
def add_table(signature, table_name, 
              source_table, source_column_name, source_pk_name,
              target_table, target_column_name, target_pk_name):
              
    columns = []
    columns.append('  "id" serial NOT NULL PRIMARY KEY')
    column_params = (source_column_name, source_table, source_pk_name)
    columns.append('  "%s" integer NOT NULL REFERENCES "%s" ("%s") DEFERRABLE INITIALLY DEFERRED'%column_params)
    column_params = (target_column_name, target_table, target_pk_name)
    columns.append('  "%s" integer NOT NULL REFERENCES "%s" ("%s") DEFERRABLE INITIALLY DEFERRED'%column_params)
    # Ok well strictly not a column
    columns.append('  UNIQUE ("%s", "%s")'%(source_column_name, target_column_name))
    return ['CREATE TABLE %s (\n%s\n);'%(table_name,',\n'.join(columns))]
    
def add_column(signature, table_name, column_name, db_type):
    params = (table_name, column_name, db_type)
    return ['ALTER TABLE %s ADD COLUMN %s %s;'%params]

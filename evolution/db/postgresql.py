
def delete_table(snapshot, table_name):
    return ['DROP TABLE %s;'%table_name]

def rename_column(snapshot, db_table, old_col_name, new_col_name):
    params = (db_table, old_col_name, new_col_name)
    return ['ALTER TABLE %s RENAME COLUMN %s TO %s;'%params]
    
def rename_table(snapshot, old_db_tablename, new_db_tablename):
    params = (old_db_tablename, new_db_tablename)
    return ['ALTER TABLE %s RENAME TO %s;'%params]
    
def delete_column(snapshot, table_name, column_name):
    params = (table_name,column_name)
    return ['ALTER TABLE %s DROP COLUMN %s CASCADE;'%params]

from django.db import connection

from common import quote_sql_param
from common import add_column, add_m2m_table, create_index
from common import delete_column, delete_table
from common import rename_table

def rename_column(opts, old_field, new_field):
    if old_field.column == new_field.column:
        # No Operation
        return []
    
    qn = connection.ops.quote_name
    params = (qn(opts.db_table), qn(old_field.column), qn(new_field.column))
    return ['ALTER TABLE %s RENAME COLUMN %s TO %s;' % params]
    
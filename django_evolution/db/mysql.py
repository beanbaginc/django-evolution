from django.core.management import color
from django.db import connection

from common import add_column, add_m2m_table, create_index
from common import delete_column, delete_table
from common import rename_table

def rename_column(opts, old_field, f):
    if old_field.column == f.column:
        # No Operation
        return []
    
    qn = connection.ops.quote_name
    style = color.no_style()
    
    ###
    col_type = f.db_type()
    tablespace = f.db_tablespace or opts.db_tablespace
    if col_type is None:
        # Skip ManyToManyFields, because they're not represented as
        # database columns in this table.
        return []
    # Make the definition (e.g. 'foo VARCHAR(30)') for this field.
    field_output = [style.SQL_FIELD(qn(f.column)),
        style.SQL_COLTYPE(col_type)]
    field_output.append(style.SQL_KEYWORD('%sNULL' % (not f.null and 'NOT ' or '')))
    if f.unique and (not f.primary_key or connection.features.allows_unique_and_pk):
        field_output.append(style.SQL_KEYWORD('UNIQUE'))
    if f.primary_key:
        field_output.append(style.SQL_KEYWORD('PRIMARY KEY'))
    if tablespace and connection.features.supports_tablespaces and (f.unique or f.primary_key) and connection.features.autoindexes_primary_keys:
        # We must specify the index tablespace inline, because we
        # won't be generating a CREATE INDEX statement for this field.
        field_output.append(connection.ops.tablespace_sql(tablespace, inline=True))
    if f.rel:
        field_output.append(style.SQL_KEYWORD('REFERENCES') + ' ' + \
            style.SQL_TABLE(qn(f.rel.to._meta.db_table)) + ' (' + \
            style.SQL_FIELD(qn(f.rel.to._meta.get_field(f.rel.field_name).column)) + ')' +
            connection.ops.deferrable_sql()
        )
        
    params = (qn(opts.db_table), qn(old_field.column), ' '.join(field_output))
    return ['ALTER TABLE %s CHANGE %s %s;' % params]

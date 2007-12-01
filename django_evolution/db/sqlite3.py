from django.core.management import color, sql
from django.db import connection, models
# NB Sqlite may allow non null column adds with a default value as part of its syntax.
from common import delete_table, rename_table, create_index, add_m2m_table
from common import add_column as common_add_column

from django_evolution.mutations import MockMeta, MockModel
from django_evolution.signature import create_project_sig, create_model_sig, create_field_sig

TEMP_TABLE_NAME = 'TEMP_TABLE'

def delete_column(model, f):
    qn = connection.ops.quote_name
    output = []
    
    field_list = model._meta.fields[:]
    for field in field_list:
        if(f.name == field.name):
            field_list.remove(field)
    table_name = model._meta.db_table
    
    output.extend(create_temp_table(field_list))
    output.extend(copy_to_temp_table(table_name, field_list))
    output.extend(delete_table(table_name))
    output.extend(create_table(table_name, field_list))
    output.extend(copy_from_temp_table(table_name, field_list))
    output.extend(delete_table(TEMP_TABLE_NAME))
    
    return output
    
def create_mock_model(model, fields):
    field_sig_dict = {}
    for f in fields:
        field_sig_dict[f.name] = create_field_sig(field)
    
    proj_sig = create_project_sig()
    model_sig = create_model_sig(model)
    model_sig['fields'] = field_sig_dict
    mock_model = MockModel(proj_sig, model.app_name, model.model_name, model_sig, stub=False)
        
def copy_to_temp_table(source_table_name, field_list):
    qn = connection.ops.quote_name
    output = [create_temp_table(field_list)]
    columns = []
    for field in field_list:
        if not models.ManyToManyField == field.__class__:
            columns.append(qn(field.column))
    column_names = ', '.join(columns)
    return ['INSERT INTO %s SELECT %s FROM %s;' % (qn(TEMP_TABLE_NAME), column_names, qn(source_table_name))]
    
def copy_from_temp_table(dest_table_name, field_list):
    qn = connection.ops.quote_name
    columns = []
    for field in field_list:
        if not models.ManyToManyField == field.__class__:
            columns.append(qn(field.column))
    column_names = ', '.join(columns)
    params = {
        'dest_table_name': qn(dest_table_name),
        'temp_table': qn(TEMP_TABLE_NAME),
        'column_names': column_names,
    }
    
    return ['INSERT INTO %(dest_table_name)s (%(column_names)s) SELECT %(column_names)s FROM %(temp_table)s;' % params]
    
def create_temp_table(field_list):
    return create_table(TEMP_TABLE_NAME, field_list, True, False)

def create_indexes_for_table(table_name, field_list):
    class FakeMeta(object):
        def __init__(self, table_name, field_list):
            self.db_table = table_name
            self.fields = field_list
            self.db_tablespace = None

    class FakeModel(object):
        def __init__(self, table_name, field_list):
            self._meta = FakeMeta(table_name, field_list)

    style = color.no_style()
    return sql.sql_indexes_for_model(FakeModel(table_name, field_list), style)
    
def create_table(table_name, field_list, temporary=False, create_index=True):
    qn = connection.ops.quote_name
    output = []
    
    create = ['CREATE']
    if temporary:
        create.append('TEMPORARY')
    create.append('TABLE %s' % qn(table_name))
    output = [' '.join(create)]
    output.append('(')
    columns = []
    for field in field_list:
        if not models.ManyToManyField == field.__class__:
            column_name = qn(field.column)
            column_type = field.db_type()
            params = [column_name, column_type]
            if field.null:
                params.append('NULL')
            else:
                params.append('NOT NULL')
            if field.unique:
                    params.append('UNIQUE')
            if field.primary_key:
                params.append('PRIMARY KEY')
            columns.append(' '.join(params))

    output.append(', '.join(columns))
    output.append(');')
    output = [''.join(output)]
    
    if create_index:
        output.extend(create_indexes_for_table(table_name, field_list))

    return output
    
def rename_column(opts, old_field, new_field):
    if old_field.column == new_field.column:
        # No Operation
        return []

    original_fields = opts.fields
    new_fields = []
    for f in original_fields:
        if f.name == old_field.name:
            new_fields.append(new_field)
        else:
            new_fields.append(f)

    table_name = opts.db_table
    output = []
    output.extend(create_temp_table(new_fields))
    output.extend(copy_to_temp_table(table_name, original_fields))
    output.extend(delete_table(table_name))
    output.extend(create_table(table_name, new_fields))
    output.extend(copy_from_temp_table(table_name, new_fields))
    output.extend(delete_table(TEMP_TABLE_NAME))
    
    return output
    
def add_column(model, f):
    # SQLite does not support the adding of unique columns.
    if not f.unique:
        return common_add_column(model,f)

    # The code below should work in all situations but the code above
    # should be more efficient so this is only done when we absolutely
    # must.
    output = []
    table_name = model._meta.db_table
    original_fields = model._meta.fields
    new_fields = original_fields
    new_fields.append(f)

    output.extend(create_temp_table(new_fields))
    output.extend(copy_to_temp_table(table_name, original_fields))
    output.extend(delete_table(table_name))
    output.extend(create_table(table_name, new_fields))
    output.extend(copy_from_temp_table(table_name, new_fields))
    output.extend(delete_table(TEMP_TABLE_NAME))
    return output

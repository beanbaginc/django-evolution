from django.db.models import get_models
from django.db.models.fields.related import *

INTERESTING_DB_ATTRIBUTES = [
    'core',
    'max_length',
    'max_digits',  #?          
    'decimal_places', #?
    'null',
    'blank',
    'db_column',
    'db_index',
    'db_tablespace',
    'primary_key',
    'unique',
]

        
def create_field_sig(field):
    field_sig = {
        'internal_type': field.get_internal_type()
    }
    if isinstance(field, ManyToManyField):
        field_sig['m2m_db_table'] = field.m2m_db_table()
    else:
        field_sig['column'] = field.column
    for attrib in INTERESTING_DB_ATTRIBUTES:
        if hasattr(field,attrib):
            field_sig[attrib] = getattr(field,attrib)
    return field_sig
    
def create_model_sig(model):
    model_sig = {
        'meta': {
            'unique_together': model._meta.unique_together
        },
        'fields': {},
    }

    for field in model._meta.fields + model._meta.many_to_many:
        model_sig['fields'][field.name] = create_field_sig(field)
    return model_sig
    
def create_app_sig(app):
    """
    Creates a dictionary representation of the models in a given app.
    Only those attributes that are interesting from a schema-evolution
    perspective are included.
    """
    app_sig = {}
    for model in get_models(app):
        app_sig[model._meta.object_name] = create_model_sig(model)
    return app_sig    


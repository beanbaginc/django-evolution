from django.db.models import get_models
from django.db.models.fields.related import *

ATTRIBUTE_DEFAULTS = {
    'core' : False,
    'max_length' : None,
    'max_digits' : None,
    'decimal_places' : None,
    'null' : None,
    'blank' : None,
    'db_column' : None,
    'db_index' : False,
    'primary_key' : False,
    'unique' : False,
    'db_tablespace' : None,
    'db_table' : None,
}

def create_field_sig_params(internal_type, name, **kwargs):
    field_sig = {
        'internal_type': internal_type,
        'name': name,
    }
        
    # It is better to bail out now if the signature to be created
    # is bad than to discover the bad signature later during a migration.
    if 'ManyToManyField' == internal_type:
        assert kwargs.has_key('m2m_db_table') and kwargs.has_key('m2m_column_name') and kwargs.has_key('m2m_reverse_name') and kwargs.has_key('related_model_class_name')
    else:
        assert kwargs.has_key('column')

    field_sig.update(kwargs)
    return field_sig

def create_field_sig(field):
    field_sig = {
        'internal_type': field.get_internal_type(),
        'name': field.name,
    }
    if isinstance(field, ManyToManyField):
        field_sig['m2m_db_table'] = field.m2m_db_table()
        field_sig['m2m_column_name'] = field.m2m_column_name()
        field_sig['m2m_reverse_name'] = field.m2m_reverse_name()
        field_sig['related_model_class_name'] = field.rel.to._meta.object_name
    else:
        field_sig['column'] = field.column
    for attrib_name in ATTRIBUTE_DEFAULTS.keys():
        if hasattr(field,attrib_name):
            attrib = getattr(field,attrib_name)
            # only store non-default values
            if not ATTRIBUTE_DEFAULTS[attrib_name] == attrib:
                field_sig[attrib_name] = attrib
    return create_field_sig_params(**field_sig)
    
def create_model_sig(model):
    opts = model._meta
    model_sig = {
        'meta': {
            'unique_together': opts.unique_together,
            'db_tablespace': opts.db_tablespace,
            'db_table': opts.db_table,
            'pk_column': opts.pk.column,
            'app_label': opts.app_label,
            'module_name': opts.module_name,
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


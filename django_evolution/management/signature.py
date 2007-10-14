from django.db.models import get_models
from django.db.models.fields.related import *

ATTRIBUTE_DEFAULTS = {
    # Common to all fields
    'primary_key': False,
    'max_length' : None,
    'unique' : False,
    'null' : False,
    'db_index' : False,
    'db_column' : None,
    'db_tablespace' : None,
    'rel': None,
    # Decimal Field
    'max_digits' : None,
    'decimal_places' : None,
    # ManyToManyField
    'db_table': None
}

def create_field_sig(field):
    field_sig = {
        'field_type': field.__class__,
    }
    # if isinstance(field, ManyToManyField):
    #     field_sig['m2m_db_table'] = field.m2m_db_table()
    #     field_sig['m2m_column_name'] = field.m2m_column_name()
    #     field_sig['m2m_reverse_name'] = field.m2m_reverse_name()
    #     field_sig['related_model_class_name'] = field.rel.to._meta.object_name
        
    for attrib in ATTRIBUTE_DEFAULTS.keys():
        if hasattr(field,attrib):
            value = getattr(field,attrib)
            if isinstance(field, ForeignKey):
                if attrib == 'db_index':
                    default = True
                else:
                    default = ATTRIBUTE_DEFAULTS[attrib]
            else:
                default = ATTRIBUTE_DEFAULTS[attrib]
            # only store non-default values
            if default != value:
                field_sig[attrib] = value
                
    rel = field_sig.pop('rel', None)
    if rel:
        field_sig['related_model'] = '.'.join([rel.to._meta.app_label, rel.to._meta.object_name])
    return field_sig
    
def create_model_sig(model):
    model_sig = {
        'meta': {
            'unique_together': model._meta.unique_together,
            'db_tablespace': model._meta.db_tablespace,
            'db_table': model._meta.db_table,
            'pk_column': model._meta.pk.column,# ??
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
    app_sig = {
        '__version__': 1,
        '__label__': app.__name__.split('.')[-2]
    }
    for model in get_models(app):
        app_sig[model._meta.object_name] = create_model_sig(model)
    return app_sig    


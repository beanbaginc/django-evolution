from django.db.models import get_models
from django.db.models.fields.related import *

INTERESTING_DB_ATTRIBUTES = [
    'core',
    'maxlength',
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

def compare_app_dicts(original, current):
    """
    Shows the differences between two representations of the model as a dict.
    """
    # This is mainly for debugging purposes 
    for key_a, value_a in original.items():
        try:
            value_b = current[key_a]
            if not value_a == value_b:
                if isinstance(value_a, dict) and isinstance(value_b, dict):
                    compare_app_dicts(value_a, value_b)
                else:
                    print 'Values do not match:'
                    print 'Key: %s\t Value:%s'%(str(key_a), str(value_a))
                    print 'Key: %s\t Value:%s'%(str(key_a), str(value_b))
                    
        except KeyError, ke:
            print current.keys()
            print 'Dictionary is missing key: %s'%key_a
    
def create_app_dict(app):
    """
    Creates a dictionary representation of the models in a given app.
    Only those attributes that are interesting from a schema-evolution
    perspective are included.
    """
    app_dict = {}
    for model in get_models(app):
        model_dict = {
            'meta': {
                'unique_together': model._meta.unique_together
            },
            'fields': {},
        }

        for field in model._meta.fields + model._meta.many_to_many:
            field_dict = {}
            field_dict['internal_type'] = field.get_internal_type()
            if isinstance(field, ManyToManyField):
                field_dict['m2m_db_table'] = field.m2m_db_table()
            else:
                field_dict['column'] = field.column
            for attrib in INTERESTING_DB_ATTRIBUTES:
                if hasattr(field,attrib):
                    field_dict[attrib] = getattr(field,attrib)
            model_dict['fields'][field.name] = field_dict

        app_dict[model._meta.object_name] = model_dict
    return app_dict

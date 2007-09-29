from django.db.models import get_models
from django.db.models.fields.related import *

from django_evolution.mutation import DeleteField

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

def create_app_sig(app):
    """
    Creates a dictionary representation of the models in a given app.
    Only those attributes that are interesting from a schema-evolution
    perspective are included.
    """
    app_sig = {}
    for model in get_models(app):
        model_sig = {
            'meta': {
                'unique_together': model._meta.unique_together
            },
            'fields': {},
        }

        for field in model._meta.fields + model._meta.many_to_many:
            field_sig = {}
            field_sig['internal_type'] = field.get_internal_type()
            if isinstance(field, ManyToManyField):
                field_sig['m2m_db_table'] = field.m2m_db_table()
            else:
                field_sig['column'] = field.column
            for attrib in INTERESTING_DB_ATTRIBUTES:
                if hasattr(field,attrib):
                    field_sig[attrib] = getattr(field,attrib)
            model_sig['fields'][field.name] = field_sig

        app_sig[model._meta.object_name] = model_sig
    return app_sig

class Diff(object):
    """
    A diff between two model signatures.
    
    The resulting diff is contained in two attributes:
    self.changed_models = { 
        model_name : {
            'added': [ list of added field names ]
            'deleted': [ list of deleted field names ]
            'changed': {
                field: [ list of modified property names ]
            }
        }
    }
    
    self.deleted_models = [ list of deleted model names ]
    """
    def __init__(self, app, original, current):
        self.app = app
        self.original_sig = original
        self.current_sig = current
        
        self.changed_models = {}
        self.deleted_models = []
        
        for model_name, old_model_sig in original.items():
            new_model_sig = current.get(model_name, None)
            if new_model_sig:
                for field_name,old_field_data in old_model_sig['fields'].items():
                    new_field_data = new_model_sig['fields'].get(field_name,None)
                    if new_field_data:
                        for prop,value in old_field_data.items():
                            if new_field_data[prop] != value:
                                # Field definition has changed
                                self.changed_models.setdefault(model_name,{}).setdefault('changed',{}).setdefault(field_name,[]).append(prop)
                    else:
                        # Field has been deleted
                        self.changed_models.setdefault(model_name,{}).setdefault('deleted',[]).append(field_name)
                    
                for field_name,new_field_data in new_model_sig['fields'].items():
                    old_field_data = old_model_sig['fields'].get(field_name,None)
                    if old_field_data is None:
                        # Field has been added
                        self.changed_models.setdefault(model_name,{}).setdefault('added',[]).append(field_name)
            else:
                # Model has been deleted
                self.deleted_models.append(model_name)
    
    def _app_label(self):
        return self.app.__name__.split('.')[-2]
    app_label = property(_app_label)
    
    def is_empty(self):
        "Is this an empty diff? i.e., is the source and target the same?"
        return not self.deleted_models and not self.changed_models
        
    def __str__(self):
        "Output an application signature diff in a human-readable format"
        lines = []
        for model in self.deleted_models:
            lines.append('The model %s.%s has been deleted' % (self.app_label, model))
        for model, change in self.changed_models.items():
            lines.append('In model %s.%s:' % (self.app_label, model))
            for name in change.get('added',[]):
                lines.append('    Field %s has been added' % name)
            for name in change.get('deleted',[]):
                lines.append('    Field %s has been deleted' % name)
            for name,field_change in change.get('changed',{}).items():
                lines.append('    In field %s:' % name)
                for prop in field_change:
                    lines.append('        Property %s has changed' % prop)
        return '\n'.join(lines)

    def evolution(self):
        "Generate an evolution that would neutralize the diff"
        mutations = []
        for model in self.deleted_models:
            # mutations.append(DeleteModel())
            pass
        for model, change in self.changed_models.items():
            for name in change.get('added',[]):
                # mutations.append(AddField())
                pass
            for name in change.get('deleted',[]):
                mutations.append(DeleteField(get_model(self.app_label, model), name))
            for name,field_change in change.get('changed',{}).items():
                # mutations.append(ChangeField())
                pass
        return mutations
        
from django_evolution.mutation import DeleteField, AddField
from django.db.models.fields.related import *

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
                mutations.append(AddField(get_model(self.app_label, model), name))
            for name in change.get('deleted',[]):
                mutations.append(DeleteField(get_model(self.app_label, model), name))
            for name,field_change in change.get('changed',{}).items():
                # mutations.append(ChangeField())
                pass
        return mutations

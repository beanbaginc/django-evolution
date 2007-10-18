from django.db import models
from django.db.models.fields.related import *

from django_evolution import EvolutionException
from django_evolution.mutations import DeleteField, AddField
from django_evolution.management.signature import ATTRIBUTE_DEFAULTS

class Diff(object):
    """
    A diff between two model signatures.
    
    The resulting diff is contained in two attributes:
    
    self.changed = {
        app_label: {
            'changed': {
                model_name : {
                    'added': [ list of added field names ]
                    'deleted': [ list of deleted field names ]
                    'changed': {
                        field: [ list of modified property names ]
                    }
                }            
            'deleted': [ list of deleted model names ] 
        }
    }
    self.deleted = {
        app_label: [ list of models in deleted app ]
    }
    """
    def __init__(self, original, current):
        self.original_sig = original
        self.current_sig = current
        
        self.changed = {}
        self.deleted = {}
        
        if self.original_sig.get('__version__', 1) != 1:
            raise EvolutionException("Unknown version identifier in original signature: %s", 
                                        self.original_sig['__version__'])
        if self.current_sig.get('__version__', 1) != 1:
            raise EvolutionException("Unknown version identifier in target signature: %s", 
                                        self.current_sig['__version__'])

        for app_name, old_app_sig in original.items():
            if app_name != '__version__':
                new_app_sig = self.current_sig.get(app_name, None)
                if new_app_sig:                
                    for model_name, old_model_sig in old_app_sig.items():
                        new_model_sig = new_app_sig.get(model_name, None)
                        if new_model_sig:
                            for field_name,old_field_data in old_model_sig['fields'].items():
                                new_field_data = new_model_sig['fields'].get(field_name,None)
                                if new_field_data:
                                    for prop,value in old_field_data.items():
                                        if new_field_data[prop] != value:
                                            # Field definition has changed
                                            self.changed.setdefault(app_name, 
                                                {}).setdefault('changed', 
                                                {}).setdefault(model_name,
                                                {}).setdefault('changed',
                                                {}).setdefault(field_name,[]).append(prop)
                                else:
                                    # Field has been deleted
                                    self.changed.setdefault(app_name, 
                                        {}).setdefault('changed', 
                                        {}).setdefault(model_name,
                                        {}).setdefault('deleted',
                                        []).append(field_name)
                    
                            for field_name,new_field_data in new_model_sig['fields'].items():
                                old_field_data = old_model_sig['fields'].get(field_name,None)
                                if old_field_data is None:
                                    # Field has been added
                                    self.changed.setdefault(app_name, 
                                        {}).setdefault('changed', 
                                        {}).setdefault(model_name,
                                        {}).setdefault('added',
                                        []).append(field_name)
                        else:
                            # Model has been deleted
                            self.changed.setdefault(app_name, 
                                {}).setdefault('deleted', 
                                []).append(model_name)
                else:
                    # App has been deleted
                    self.deleted[app_name] = old_app_sig.keys()
                    
    def is_empty(self):
        "Is this an empty diff? i.e., is the source and target the same?"
        return not self.deleted and not self.changed
        
    def __str__(self):
        "Output an application signature diff in a human-readable format"
        lines = []
        for app_label in self.deleted:
            lines.append('The application %s has been deleted' % app_label)
        for app_label, app_changes in self.changed.items():
            for model_name in app_changes.get('deleted', {}):
                lines.append('The model %s.%s has been deleted' % (app_label, model_name))
            for model_name, change in app_changes.get('changed', {}).items():
                lines.append('In model %s.%s:' % (app_label, model_name))
                for field_name in change.get('added',[]):
                    lines.append("    Field '%s' has been added" % field_name)
                for field_name in change.get('deleted',[]):
                    lines.append("    Field '%s' has been deleted" % field_name)
                for field_name,field_change in change.get('changed',{}).items():
                    lines.append("    In field '%s':" % field_name)
                    for prop in field_change:
                        lines.append("        Property '%s' has changed" % prop)
        return '\n'.join(lines)

    def evolution(self):
        "Generate an evolution that would neutralize the diff"
        mutations = {}
        for app_label, model_names in self.deleted.items():
            # mutations.setdefault(app_label,[]).append(DeleteModel(model_name))
            pass
        for app_label, app_changes in self.changed.items():
            for model_name in app_changes.get('deleted',{}):
                # mutations.setdefault(app_label,[]).append(DeleteModel(model_name))
                pass                
            for model_name, change in app_changes.get('changed',{}).items():
                for field_name in change.get('added',{}):
                    field_sig = self.current_sig[app_label][model_name]['fields'][field_name]
                    add_params = [(key,field_sig[key]) for key in field_sig.keys() if key in ATTRIBUTE_DEFAULTS.keys()]
                    add_params.append(('field_type', field_sig['field_type']))
                    if 'related_model' in field_sig:
                        add_params.append(('related_model', '%s' % field_sig['related_model']))
                    mutations.setdefault(app_label,[]).append(
                        AddField(model_name, field_name, **dict(add_params)))
                for field_name in change.get('deleted',[]):
                    mutations.setdefault(app_label,[]).append(
                        DeleteField(model_name, field_name))
                for field_name,field_change in change.get('changed',{}).items():
                    # mutations.setdefault(app_label,[]).append(ChangeField())
                    pass
        
        return mutations

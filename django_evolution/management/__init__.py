try:
    import cPickle as pickle
except ImportError:
    import pickle as pickle

from django.dispatch import dispatcher
from django.core.management.color import color_style
from django.db.models import signals

from django_evolution import models as django_evolution
from django_evolution.management.signature import create_project_sig
from django_evolution.management.diff import Diff
style = color_style()
    
def evolution(app, created_models, verbosity=1):
    """
    A hook into syncdb's post_syncdb signal, that is used to notify the user
    if a model evolution is necessary.
    """
    # Evolutions are checked over the entire project, so we only need to 
    # check once. We do this check when Django Evolutions itself is synchronized.
    if app == django_evolution:        
        proj_sig = create_project_sig()
        signature = pickle.dumps(proj_sig)

        try:
            latest_evolution = django_evolution.Evolution.objects.latest('when')

            # TODO: Model introspection step goes here. 
            # # If the current database state doesn't match the last 
            # # saved signature (as reported by latest_evolution),
            # # then we need to update the Evolution table.
            # actual_sig = introspect_project_sig()
            # acutal = pickle.dumps(actual_sig)
            # if actual != latest_evolution.signature:
            #     nudge = Evolution(signature=actual)
            #     nudge.save()
            #     latest_evolution = nudge
            
            if latest_evolution.signature != signature:
                # Signatures do not match - an evolution is required. 
                print style.NOTICE('Models have changed - an evolution is required')
                if verbosity > 1:
                    old_proj_sig = pickle.loads(str(latest_evolution.signature))
                    print Diff(old_proj_sig, proj_sig)
            else:
                if verbosity > 1:
                    print "No evolutions required"
        except django_evolution.Evolution.DoesNotExist:
            # This is the first time that this project has been seen
            # We need to create a baseline Evolution entry.

            # In general there will be an application label and app_sig to save. The
            # exception to the rule is for empty models (such as in the django tests).
            try:                
                version = len(settings.EVOLUTION_SEQUENCE)
            except:
                version = 0
            if verbosity > 0:
                print "Installing baseline evolution (Version %d)" % version
            evolution = django_evolution.Evolution(version=version, signature=signature)
            evolution.save()
dispatcher.connect(evolution, signal=signals.post_syncdb)

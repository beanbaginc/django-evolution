try:
    import cPickle as pickle
except ImportError:
    import pickle as pickle

from django.dispatch import dispatcher
from django.core.management.color import color_style
from django.db.models import signals

from django_evolution.models import Evolution
from django_evolution.management.signature import compare_app_dicts, create_app_dict
style = color_style()
    
def evolution(app, created_models, verbosity=1):
    """
    A hook into syncdb's post_syncdb signal, that is used to notify the user
    if a model evolution is necessary.
    """
    app_name = '.'.join(app.__name__.split('.')[:-1])
    app_dict = create_app_dict(app)
    signature = pickle.dumps(app_dict)

    evolutions = Evolution.objects.filter(app_name=app_name)
    if len(evolutions) > 0:
        last_evolution = evolutions[0]
        if last_evolution.signature != signature:
            # Signatures do not match - an evolution is required. 
            print style.NOTICE('Models in %s have changed - an evolution is required' % app_name)
            if verbosity > 1:
                old_app_dict = pickle.loads(str(last_evolution.signature))
                compare_app_dicts(old_app_dict, app_dict)
        else:
            if verbosity > 1:
                print "No evolution required for application %s" % app_name
    else:
        # This is the first time that this application has been seen
        # We need to create a baseline Evolution entry.

        # In general there will be an application label and app_dict to save. The
        # exception to the rule is for empty models (such as in the django tests).
        if app_dict:
            if verbosity > 1:
                print "Install baseline evolution entry for application %s" % app_name
            evolution = Evolution(app_name=app_name,version=0,signature=signature)
            evolution.save()
    
dispatcher.connect(evolution, signal=signals.post_syncdb)

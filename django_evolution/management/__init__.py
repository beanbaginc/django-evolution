try:
    import cPickle as pickle
except ImportError:
    import pickle as pickle

from django.dispatch import dispatcher
from django.core.management.color import color_style
from django.db.models import signals, get_apps

from django_evolution import models as django_evolution
from django_evolution.evolve import get_evolution_sequence, get_unapplied_evolutions
from django_evolution.signature import create_project_sig
from django_evolution.diff import Diff

style = color_style()
    
def evolution(app, created_models, verbosity=1):
    """
    A hook into syncdb's post_syncdb signal, that is used to notify the user
    if a model evolution is necessary.
    """
    proj_sig = create_project_sig()
    signature = pickle.dumps(proj_sig)

    try:
        latest_version = django_evolution.Version.objects.latest('when')
    except django_evolution.Version.DoesNotExist:
        # We need to create a baseline version.
        if verbosity > 0:
            print "Installing baseline version"

        latest_version = django_evolution.Version(signature=signature)
        latest_version.save()

        for a in get_apps():
            app_label = a.__name__.split('.')[-2]
            sequence = get_evolution_sequence(a)
            if sequence:
                if verbosity > 0:
                    print 'Evolutions in %s baseline:' % app_label,', '.join(sequence)
            for evo_label in sequence:
                evolution = django_evolution.Evolution(app_label=app_label, 
                                                       label=evo_label,
                                                       version=latest_version)
                evolution.save()

    unapplied = get_unapplied_evolutions(app)
    if unapplied:
        print style.NOTICE('There are unapplied evolutions for %s.' % app.__name__.split('.')[-2])
        
    # Evolutions are checked over the entire project, so we only need to 
    # check once. We do this check when Django Evolutions itself is synchronized.
    if app == django_evolution: 
        # TODO: Model introspection step goes here. 
        # # If the current database state doesn't match the last 
        # # saved signature (as reported by latest_version),
        # # then we need to update the Evolution table.
        # actual_sig = introspect_project_sig()
        # acutal = pickle.dumps(actual_sig)
        # if actual != latest_version.signature:
        #     nudge = Version(signature=actual)
        #     nudge.save()
        #     latest_version = nudge
        if latest_version.signature != signature:
            # Signatures do not match - an evolution is required. 
            print style.NOTICE('Project signature has changed - an evolution is required')
            if verbosity > 1:
                old_proj_sig = pickle.loads(str(latest_version.signature))
                print Diff(old_proj_sig, proj_sig)

dispatcher.connect(evolution, signal=signals.post_syncdb)

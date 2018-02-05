from __future__ import print_function, unicode_literals

import logging

import django
from django.conf import settings
from django.core.management.color import color_style
from django.db.models import signals
from django.db.utils import DEFAULT_DB_ALIAS
from django.utils import six

from django_evolution import models as django_evolution
from django_evolution.compat.apps import get_apps, get_app
from django_evolution.compat.py23 import pickle_dumps, pickle_loads
from django_evolution.diff import Diff
from django_evolution.evolve import (get_evolution_sequence,
                                     get_unapplied_evolutions)
from django_evolution.signature import create_project_sig
from django_evolution.utils import get_app_label


style = color_style()


def _install_baseline(app, latest_version, using, verbosity):
    """Install baselines for an app.

    This goes through the entire evolution sequence for an app and records
    each evolution as being applied, creating a baseline for any apps that
    are newly-added whose models have just been created (or existed prior to
    using Django Evolution).

    Args:
        app (module):
            The app models module.

        latest_version (django_evolution.models.Version):
            The latest version, which the evolutions will be associated with.

        using (str):
            The database being updated.

        verbosity (int):
            The verbosity used to control output.
    """
    app_label = get_app_label(app)
    sequence = get_evolution_sequence(app)

    if sequence and verbosity > 0:
        print('Evolutions in %s baseline: %s' % (app_label,
                                                 ', '.join(sequence)))

    for evo_label in sequence:
        evolution = django_evolution.Evolution(app_label=app_label,
                                               label=evo_label,
                                               version=latest_version)
        evolution.save(using=using)


def _on_app_models_updated(app, verbosity=1, using=DEFAULT_DB_ALIAS, **kwargs):
    """Handler for when an app's models were updated.

    This is called in response to a syncdb or migrate operation for an app.
    It will install baselines for any new models, record the changes in the
    evolution history, and notify the user if any of the changes require an
    evolution.

    Args:
        app (module):
            The app models module that was updated.

        verbosity (int, optional):
            The verbosity used to control output. This will have been provided
            by the syncdb or migrate command.

        using (str, optional):
            The database being updated.

        **kwargs (dict):
            Additional keyword arguments provided by the signal handler for
            the syncdb or migrate operation.
    """
    proj_sig = create_project_sig(using)
    signature = pickle_dumps(proj_sig)

    try:
        latest_version = \
            django_evolution.Version.objects.current_version(using=using)
    except django_evolution.Version.DoesNotExist:
        # We need to create a baseline version.
        if verbosity > 0:
            print("Installing baseline version")

        latest_version = django_evolution.Version(signature=signature)
        latest_version.save(using=using)

        for a in get_apps():
            _install_baseline(app=a,
                              latest_version=latest_version,
                              using=using,
                              verbosity=verbosity)

    unapplied = get_unapplied_evolutions(app, using)

    if unapplied:
        print(style.NOTICE('There are unapplied evolutions for %s.'
                           % get_app_label(app)))

    # Evolutions are checked over the entire project, so we only need to check
    # once. We do this check when Django Evolutions itself is synchronized.
    if app == django_evolution:
        old_proj_sig = pickle_loads(latest_version.signature)

        # If any models or apps have been added, a baseline must be set
        # for those new models
        changed = False
        new_apps = []

        for app_name, new_app_sig in six.iteritems(proj_sig):
            if app_name == '__version__':
                # Ignore the __version__ tag
                continue

            old_app_sig = old_proj_sig.get(app_name, None)

            if old_app_sig is None:
                # App has been added
                old_proj_sig[app_name] = proj_sig[app_name]
                new_apps.append(app_name)
                changed = True
            else:
                for model_name, new_model_sig in six.iteritems(new_app_sig):
                    old_model_sig = old_app_sig.get(model_name, None)

                    if old_model_sig is None:
                        # Model has been added
                        old_proj_sig[app_name][model_name] = \
                            proj_sig[app_name][model_name]
                        changed = True

        if changed:
            if verbosity > 0:
                print("Adding baseline version for new models")

            latest_version = \
                django_evolution.Version(signature=pickle_dumps(old_proj_sig))
            latest_version.save(using=using)

            for app_name in new_apps:
                app = get_app(app_name, True)

                if app:
                    _install_baseline(app=app,
                                      latest_version=latest_version,
                                      using=using,
                                      verbosity=verbosity)

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

        diff = Diff(old_proj_sig, proj_sig)

        if not diff.is_empty():
            print(style.NOTICE(
                'Project signature has changed - an evolution is required'))

            if verbosity > 1:
                old_proj_sig = pickle_loads(str(latest_version.signature))
                print(diff)


def _on_post_syncdb(app, **kwargs):
    """Handler to install baselines after syncdb has completed.

    This will install baselines for any new apps, once syncdb has completed
    for the app, and will notify the user if any evolutions are required.

    Args:
        app (module):
            The app whose models were migrated.

        **kwargs (dict):
            Keyword arguments passed to the signal handler.
    """
    _on_app_models_updated(app=app,
                           using=kwargs.get('db', DEFAULT_DB_ALIAS),
                           **kwargs)


def _on_post_migrate(app_config, **kwargs):
    """Handler to install baselines after app migration has completed.

    This works like the syncdb handler to install baselines for any new apps,
    once the app's model migration has completed, and to notify if any
    evolutions are required.

    Args:
        app_config (django.apps.AppConfig):
            The configuration for the app whose models were migrated.

        **kwargs (dict):
            Keyword arguments passed to the signal handler.
    """
    _on_app_models_updated(app=app_config.models_module, **kwargs)


if getattr(settings, 'DJANGO_EVOLUTION_ENABLED', True):
    if hasattr(signals, 'post_syncdb'):
        signals.post_syncdb.connect(_on_post_syncdb)
    elif hasattr(signals, 'post_migrate'):
        signals.post_migrate.connect(_on_post_migrate)
    else:
        logging.error('Django Evolution cannot automatically install '
                      'baselines or evolve on Django %s',
                      django.get_version())

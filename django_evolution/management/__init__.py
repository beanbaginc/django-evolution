from __future__ import print_function, unicode_literals

import logging

import django
from django.conf import settings
from django.db.models import signals
from django.db.utils import DEFAULT_DB_ALIAS
from django.dispatch import receiver

from django_evolution.compat.apps import get_apps, get_app
from django_evolution.evolve import Evolver
from django_evolution.models import Evolution, Version
from django_evolution.signals import evolved, evolving, evolving_failed
from django_evolution.utils.apps import get_app_label
from django_evolution.utils.evolutions import get_evolution_sequence


django_evolution_app = get_app('django_evolution')


_evolve_lock = 0


@receiver(evolving)
def _on_evolving(**kwargs):
    """Handler for when an Evolver begins evolving.

    This will increment a lock, used to determine whether to react to any
    Django post-migrate/syncdb signals.

    Args:
        **kwargs (dict):
            Keyword arguments passed to the signal.
    """
    global _evolve_lock

    _evolve_lock += 1


@receiver([evolved, evolving_failed])
def _on_evolving_done(**kwargs):
    """Handler for when an Evolver finishes evolving.

    This will decrement a lock, used to determine whether to react to any
    Django post-migrate/syncdb signals.

    Args:
        **kwargs (dict):
            Keyword arguments passed to the signal.
    """
    global _evolve_lock

    _evolve_lock -= 1


def _on_app_models_updated(app, using=DEFAULT_DB_ALIAS, **kwargs):
    """Handler for when an app's models were updated.

    This is called in response to a syncdb or migrate operation for an app.
    The very first time this is called for Django Evolution's app, this will
    set up the current project version to contain the full database signature,
    and to populate the list of evolutions with all currently-registered ones.

    This is only done when we're not actively evolving the database. That
    means it will only be called if we're running unit tests or in reaction
    to some other process that emits the signals (such as the flush management
    command).

    Args:
        app (module):
            The app models module that was updated.

        using (str, optional):
            The database being updated.

        **kwargs (dict):
            Additional keyword arguments provided by the signal handler for
            the syncdb or migrate operation.
    """
    if (_evolve_lock > 0 or
        app is not django_evolution_app or
        Version.objects.using(using).exists()):
        return

    evolver = Evolver(database_name=using)

    version = evolver.version
    version.signature = evolver.target_project_sig
    version.save(using=using)

    evolutions = []

    for app in get_apps():
        app_label = get_app_label(app)

        evolutions += [
            Evolution(app_label=app_label,
                      label=evolution_label,
                      version=version)
            for evolution_label in get_evolution_sequence(app)
        ]

    Evolution.objects.using(using).bulk_create(evolutions)


def _on_post_syncdb(app, **kwargs):
    """Handler to install baselines after syncdb has completed.

    This wraps :py:func:`_on_app_models_updated`.

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

    This wraps :py:func:`_on_app_models_updated`.

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

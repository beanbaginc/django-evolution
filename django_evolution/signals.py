"""Signals for monitoring the evolution process."""

from __future__ import unicode_literals

from django.dispatch import Signal


#: Emitted when an Evolver begins evolving.
evolving = Signal()

#: Emitted when an Evolver finishes evolving.
evolved = Signal()

#: Emitted when an Evolver fails evolving.
#:
#: Args:
#:     exception (Exception):
#:         The exception raised when evolution failed.
evolving_failed = Signal(providing_args=['exception'])

#: Emitted when an evolution is about to be applied to an app.
#:
#: Args:
#:     app_label (unicode):
#:         The label of the application being applied.
#:
#:     task (django_evolution.evolve.EvolveAppTask):
#:         The task evolving the app.
applying_evolution = Signal(providing_args=['app_label', 'task'])

#: Emitted when an evolution has been applied to an app.
#:
#: Args:
#:     app_label (unicode):
#:         The label of the application being applied.
#:
#:     task (django_evolution.evolve.EvolveAppTask):
#:         The task that evolved the app.
applied_evolution = Signal(providing_args=['app_label', 'task'])

#: Emitted when a migration is about to be applied to an app.
#:
#: Args:
#:     migration (django.db.migrations.migration.Migration):
#:         The migration that's being applied.
applying_migration = Signal(providing_args=['migration'])

#: Emitted when a migration has been applied to an app.
#:
#: Args:
#:     migration (django.db.migrations.migration.Migration):
#:         The migration that was applied.
applied_migration = Signal(providing_args=['migration'])

#: Emitted when creating new models for an app outside of a migration.
#:
#: Args:
#:     app_label (unicode):
#:         The app label for the models being created.
#:
#:     model_names (list of unicode):
#:         The list of models being created.
creating_models = Signal(providing_args=['app_label', 'model_names'])

#: Emitted when finished creating new models for an app outside of a migration.
#:
#: Args:
#:     migration (django.db.migrations.migration.Migration):
#:         The migration that was applied.
#:
#:     model_names (list of unicode):
#:         The list of models that were created.
created_models = Signal(providing_args=['app_label', 'model_names'])

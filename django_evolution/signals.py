"""Signals for monitoring the evolution process."""

from __future__ import unicode_literals

from django.dispatch import Signal


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

"""Mutation that moves an app to Django migrations.

Version Added:
    2.2
"""

from __future__ import unicode_literals

from django_evolution.consts import UpgradeMethod
from django_evolution.mutations.base import BaseUpgradeMethodMutation


class MoveToDjangoMigrations(BaseUpgradeMethodMutation):
    """A mutation that uses Django migrations for an app's future upgrades.

    This directs this app to evolve only up until this mutation, and to then
    hand any future schema changes over to Django's migrations.

    Once this mutation is used, no further mutations can be added for the app.

    Version Changed:
        2.2:
        Moved into the
        :py:mod:`django_evolution.mutations.move_to_django_migrations` module.
    """

    def __init__(self, mark_applied=['0001_initial']):
        """Initialize the mutation.

        Args:
            mark_applied (unicode, optional):
                The list of migrations to mark as applied. Each of these
                should have been covered by the initial table or subsequent
                evolutions. By default, this covers the ``0001_initial``
                migration.
        """
        self.mark_applied = set(mark_applied)

    def generate_dependencies(self, app_label, **kwargs):
        """Return automatic dependencies for the parent evolution.

        This will generate a dependency forcing this evolution to apply
        before the migrations that are marked as applied, ensuring that
        subsequent migrations are applied in the correct order.

        Version Added:
            2.1

        Args:
            app_label (unicode):
                The label of the app containing this mutation.

            **kwargs (dict):
                Additional keyword arguments, for future use.

        Returns:
            dict:
            A dictionary of dependencies. This may have zero or more of the
            following keys:

            * ``before_migrations``
            * ``after_migrations``
            * ``before_evolutions``
            * ``after_evolutions``
        """
        # We set this to execute after the migrations to handle the following
        # conditions:
        #
        # 1. If this app is being installed into the database for the first
        #    time, we want the migrations to handle it, and therefore want
        #    to make sure those operations happen first. This evolution and
        #    prior ones in the sequence will themselves be marked as applied,
        #    but won't make any changes to the database.
        #
        # 2. If the app was already installed, but this evolution is new and
        #    being applied for the first time, we'll have already installed
        #    the equivalent of these migrations that are being marked as
        #    applied. We'll want to make sure we've properly set up the
        #    graph for those migrations before we continue on with any
        #    migrations *after* the ones we're marking as applied. Otherwise,
        #    the order of dependencies and evolutions can end up being wrong.
        return {
            'after_migrations': set(
                (app_label, migration_name)
                for migration_name in self.mark_applied
            )
        }

    def simulate(self, simulation):
        """Simulate the mutation.

        This will alter the app's signature to mark it as being handled by
        Django migrations.

        Args:
            simulation (Simulation):
                The simulation being performed.
        """
        app_sig = simulation.get_app_sig()
        app_sig.upgrade_method = UpgradeMethod.MIGRATIONS
        app_sig.applied_migrations = self.mark_applied

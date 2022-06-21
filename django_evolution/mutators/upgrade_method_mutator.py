"""Mutator that changes the upgrade method of an app."""

from __future__ import unicode_literals

from django_evolution.mutations.base import BaseUpgradeMethodMutation
from django_evolution.mutators.base import BaseAppStateMutator


class UpgradeMethodMutator(BaseAppStateMutator):
    """Changes the upgrade method of an app.

    This is used by the app mutator to track mutations that change the upgrade
    method, and to ensure that a simulation is run during the finalization
    process in order to apply changes back to the signature.

    Version Changed:
        2.2
    """

    def __init__(self, app_mutator, mutation):
        """Initialize the mutator.

        Args:
            app_mutator (django_evolution.mutators.app_mutator.AppMutator):
                The parent app mutator.

            mutation (django_evolution.mutations.base.
                      BaseUpgradeMethodMutation):
                The mutation that this mutator will manage.
        """
        assert isinstance(mutation, BaseUpgradeMethodMutation)

        super(UpgradeMethodMutator, self).__init__(app_mutator=app_mutator)

        self._mutation = mutation

    def finalize(self):
        """Finalize the mutator.

        This will finalize the object and then run a final simulation to update
        the signature.

        After the mutator is finalized, no new state can be scheduled or
        modified.
        """
        super(UpgradeMethodMutator, self).finalize()

        self.run_simulation(self._mutation)

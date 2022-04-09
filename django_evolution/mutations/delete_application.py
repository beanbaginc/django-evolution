"""Mutation that deletes an application.

Version Added:
    2.2
"""

from __future__ import unicode_literals

from django_evolution.mutations.base import BaseMutation
from django_evolution.mutations.delete_model import DeleteModel


class DeleteApplication(BaseMutation):
    """A mutation that deletes an application.

    Version Changed:
        2.2:
        Moved into the :py:mod:`django_evolution.mutations.delete_application`
        module.
    """

    simulation_failure_error = \
        'Cannot delete the application "%(app_label)s".'

    def simulate(self, simulation):
        """Simulate the mutation.

        This will alter the database schema to delete the specified
        application.

        Args:
            simulation (Simulation):
                The state for the simulation.

        Raises:
            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message.
        """
        if not simulation.database:
            return

        app_sig = simulation.get_app_sig()

        # Simulate the deletion of the models.
        for model_sig in list(app_sig.model_sigs):
            model_name = model_sig.model_name
            mutation = DeleteModel(model_name)

            if mutation.is_mutable(app_label=simulation.app_label,
                                   project_sig=simulation.project_sig,
                                   database_state=simulation.database_state,
                                   database=simulation.database):
                # Check for the model's existence, and then delete.
                simulation.get_model_sig(model_name)
                app_sig.remove_model_sig(model_name)

    def mutate(self, mutator):
        """Schedule an application deletion on the mutator.

        This will instruct the mutator to delete an application, if it exists.
        It will be scheduled and later executed on the database, if not
        optimized out.

        Args:
            mutator (django_evolution.mutators.AppMutator):
                The mutator to perform an operation on.
        """
        # This test will introduce a regression, but we can't afford to remove
        # all models at a same time if they aren't owned by the same database
        if mutator.database:
            app_sig = mutator.project_sig.get_app_sig(mutator.app_label)

            for model_sig in list(app_sig.model_sigs):
                model_name = model_sig.model_name
                mutation = DeleteModel(model_name)

                if mutation.is_mutable(app_label=mutator.app_label,
                                       project_sig=mutator.project_sig,
                                       database_state=mutator.database_state,
                                       database=mutator.database):
                    mutator.run_mutation(mutation)

    def is_mutable(self, *args, **kwargs):
        """Return whether the mutation can be applied to the database.

        This will always return true. The mutation will safely handle the
        application no longer being around.

        Args:
            *args (tuple, unused):
                Positional arguments passed to the function.

            **kwargs (dict, unused):
                Keyword arguments passed to the function.

        Returns:
            bool:
            ``True``, always.
        """
        return True

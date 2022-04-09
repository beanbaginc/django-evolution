"""Mutation that deletes a model.

Version Added:
    2.2
"""

from __future__ import unicode_literals

from django.db import models

from django_evolution.db.sql_result import SQLResult
from django_evolution.mutations.base import BaseModelMutation


class DeleteModel(BaseModelMutation):
    """A mutation that deletes a model.

    Version Changed:
        2.2:
        Moved into the :py:mod:`django_evolution.mutations.delete_model`
        module.
    """

    simulation_failure_error = \
        'Cannot delete the model "%(app_label)s.%(model_name)s".'

    def get_hint_params(self):
        """Return parameters for the mutation's hinted evolution.

        Returns:
            list of unicode:
            A list of parameter strings to pass to the mutation's constructor
            in a hinted evolution.
        """
        return [self.serialize_value(self.model_name)]

    def simulate(self, simulation):
        """Simulate the mutation.

        This will alter the database schema to delete the specified model.

        Args:
            simulation (Simulation):
                The state for the simulation.

        Raises:
            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message.
        """
        app_sig = simulation.get_app_sig()

        # Check for the model first, and then delete it.
        simulation.get_model_sig(self.model_name)
        app_sig.remove_model_sig(self.model_name)

    def mutate(self, mutator, model):
        """Schedule a model deletion on the mutator.

        This will instruct the mutator to delete a model. It will be scheduled
        and later executed on the database, if not optimized out.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.
        """
        sql_result = SQLResult()

        # Remove any many-to-many tables.
        for field_sig in mutator.model_sig.field_sigs:
            if issubclass(field_sig.field_type, models.ManyToManyField):
                field = model._meta.get_field(field_sig.field_name)
                m2m_table = field._get_m2m_db_table(model._meta)
                sql_result.add(mutator.evolver.delete_table(m2m_table))

        # Remove the table itself.
        sql_result.add(mutator.evolver.delete_table(model._meta.db_table))

        mutator.add_sql(self, sql_result)

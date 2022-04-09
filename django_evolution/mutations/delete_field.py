"""Mutation for deleting fields from a model.

Version Added:
    2.2
"""

from __future__ import unicode_literals

from django.db import models

from django_evolution.mock_models import create_field
from django_evolution.mutations.base import BaseModelFieldMutation


class DeleteField(BaseModelFieldMutation):
    """A mutation that deletes a field from a model.

    Version Changed:
        2.2:
        Moved into the :py:mod:`django_evolution.mutations.delete_field`
        module.
    """

    simulation_failure_error = (
        'Cannot delete the field "%(field_name)s" on model '
        '"%(app_label)s.%(model_name)s".'
    )

    def get_hint_params(self):
        """Return parameters for the mutation's hinted evolution.

        Returns:
            list of unicode:
            A list of parameter strings to pass to the mutation's constructor
            in a hinted evolution.
        """
        return [
            self.serialize_value(self.model_name),
            self.serialize_value(self.field_name),
        ]

    def simulate(self, simulation):
        """Simulate the mutation.

        This will alter the database schema to remove the specified field,
        modifying meta fields (``unique_together``) if necessary.

        It will also check to make sure this is not a primary key and that
        the field exists.

        Args:
            simulation (Simulation):
                The state for the simulation.

        Raises:
            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message.
        """
        model_sig = simulation.get_model_sig(self.model_name)
        field_sig = simulation.get_field_sig(self.model_name, self.field_name)

        if field_sig.get_attr_value('primary_key'):
            simulation.fail('The field is a primary key and cannot '
                            'be deleted.')

        # If the field was used in the unique_together attribute, update it.
        new_unique_together = []

        for unique_together_entry in model_sig.unique_together:
            new_entry = tuple(
                field_name
                for field_name in unique_together_entry
                if field_name != self.field_name
            )

            if new_entry:
                new_unique_together.append(new_entry)

        model_sig.unique_together = new_unique_together

        # Simulate the deletion of the field.
        model_sig.remove_field_sig(self.field_name)

    def mutate(self, mutator, model):
        """Schedule a field deletion on the mutator.

        This will instruct the mutator to perform a deletion of a field on
        a model. It will be scheduled and later executed on the database, if
        not optimized out.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.
        """
        field_sig = mutator.model_sig.get_field_sig(self.field_name)
        field = create_field(project_sig=mutator.project_sig,
                             field_name=self.field_name,
                             field_type=field_sig.field_type,
                             field_attrs=field_sig.field_attrs,
                             parent_model=model,
                             related_model=field_sig.related_model)

        if isinstance(field, models.ManyToManyField):
            mutator.add_sql(
                self,
                mutator.evolver.delete_table(
                    field._get_m2m_db_table(model._meta)))
        else:
            mutator.delete_column(self, field)

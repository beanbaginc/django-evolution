"""Mutation that changes attributes on a field.

Version Added:
    2.2
"""

from __future__ import unicode_literals

from django.db import models

from django_evolution.compat import six
from django_evolution.errors import EvolutionNotImplementedError
from django_evolution.mutations.base import BaseModelFieldMutation


class ChangeField(BaseModelFieldMutation):
    """A mutation that changes attributes on a field on a model.

    Version Changed:
        2.2:
        Moved into the :py:mod:`django_evolution.mutations.change_field`
        module.
    """

    simulation_failure_error = (
        'Cannot change the field "%(field_name)s" on model '
        '"%(app_label)s.%(model_name)s".'
    )

    def __init__(self, model_name, field_name, initial=None, **field_attrs):
        """Initialize the mutation.

        Args:
            model_name (unicode):
                The name of the model containing the field to change.

            field_name (unicode):
                The name of the field to change.

            initial (object, optional):
                The initial value for the field. This is required if non-null.

            **field_attrs (dict):
                Attributes to set on the field.
        """
        super(ChangeField, self).__init__(model_name, field_name)

        self.field_attrs = field_attrs
        self.initial = initial

    def get_hint_params(self):
        """Return parameters for the mutation's hinted evolution.

        Returns:
            list of unicode:
            A list of parameter strings to pass to the mutation's constructor
            in a hinted evolution.
        """
        params = [
            self.serialize_attr(attr_name, attr_value)
            for attr_name, attr_value in six.iteritems(self.field_attrs)
        ] + [
            self.serialize_attr('initial', self.initial),
        ]

        return [
            self.serialize_value(self.model_name),
            self.serialize_value(self.field_name),
        ] + sorted(params)

    def simulate(self, simulation):
        """Simulate the mutation.

        This will alter the database schema to change attributes for the
        specified field.

        Args:
            simulation (Simulation):
                The state for the simulation.

        Raises:
            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message.
        """
        field_sig = simulation.get_field_sig(self.model_name, self.field_name)
        field_sig.field_attrs.update(self.field_attrs)

        if ('null' in self.field_attrs and not self.field_attrs['null'] and
            not issubclass(field_sig.field_type, models.ManyToManyField) and
            self.initial is None):
            simulation.fail('A non-null initial value needs to be specified '
                            'in the mutation.')

    def mutate(self, mutator, model):
        """Schedule a field change on the mutator.

        This will instruct the mutator to change attributes on a field on a
        model. It will be scheduled and later executed on the database, if not
        optimized out.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.
        """
        field_sig = mutator.model_sig.get_field_sig(self.field_name)
        field = model._meta.get_field(self.field_name)

        for attr_name in six.iterkeys(self.field_attrs):
            if attr_name not in mutator.evolver.supported_change_attrs:
                raise EvolutionNotImplementedError(
                    "ChangeField does not support modifying the '%s' "
                    "attribute on '%s.%s'."
                    % (attr_name, self.model_name, self.field_name))

        new_field_attrs = {}

        for attr_name, attr_value in six.iteritems(self.field_attrs):
            old_attr_value = field_sig.get_attr_value(attr_name)

            # Avoid useless SQL commands if nothing has changed.
            if old_attr_value != attr_value:
                new_field_attrs[attr_name] = {
                    'old_value': old_attr_value,
                    'new_value': attr_value,
                }

        if new_field_attrs:
            mutator.change_column(self, field, new_field_attrs)

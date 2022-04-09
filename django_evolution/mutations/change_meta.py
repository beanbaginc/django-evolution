"""Mutation that changes meta properties on a model.

Version Added:
    2.2
"""

from __future__ import unicode_literals

from django_evolution.compat import six
from django_evolution.compat.datastructures import OrderedDict
from django_evolution.mutations.base import BaseModelMutation
from django_evolution.signature import (ConstraintSignature,
                                        IndexSignature)


class ChangeMeta(BaseModelMutation):
    """A mutation that changes meta properties on a model.

    Version Changed:
        2.2:
        Moved into the :py:mod:`django_evolution.mutations.change_meta` module.
    """

    simulation_failure_error = (
        'Cannot change the "%(prop_name)s" meta property on model '
        '"%(app_label)s.%(model_name)s".'
    )

    error_vars = dict({
        'prop_name': 'prop_name',
    }, **BaseModelMutation.error_vars)

    def __init__(self, model_name, prop_name, new_value):
        """Initialize the mutation.

        Args:
            model_name (unicode):
                The name of the model to change meta properties on.

            prop_name (unicode):
                The name of the property to change.

            new_value (object):
                The new value for the property.
        """
        super(ChangeMeta, self).__init__(model_name)

        self.prop_name = prop_name
        self.new_value = new_value

    def get_hint_params(self):
        """Return parameters for the mutation's hinted evolution.

        Returns:
            list of unicode:
            A list of parameter strings to pass to the mutation's constructor
            in a hinted evolution.
        """
        if self.prop_name in ('index_together', 'unique_together'):
            # Make sure these always appear as lists and not tuples, for
            # compatibility.
            norm_value = list(self.new_value)
        elif self.prop_name == 'constraints':
            # Django >= 2.2
            norm_value = [
                OrderedDict(sorted(six.iteritems(constraint_data),
                                   key=lambda pair: pair[0]))
                for constraint_data in self.new_value
            ]
        elif self.prop_name == 'indexes':
            # Django >= 1.11
            norm_value = [
                OrderedDict(sorted(six.iteritems(index_data),
                                   key=lambda pair: pair[0]))
                for index_data in self.new_value
            ]
        else:
            norm_value = self.new_value

        return [
            self.serialize_value(self.model_name),
            self.serialize_value(self.prop_name),
            self.serialize_value(norm_value),
        ]

    def simulate(self, simulation):
        """Simulate the mutation.

        This will alter the database schema to change metadata on the specified
        model.

        Args:
            simulation (Simulation):
                The state for the simulation.

        Raises:
            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message.
        """
        model_sig = simulation.get_model_sig(self.model_name)
        evolver = simulation.get_evolver()
        prop_name = self.prop_name

        if not evolver.supported_change_meta.get(prop_name):
            simulation.fail('The property cannot be modified on this '
                            'database.')

        if prop_name == 'index_together':
            model_sig.index_together = self.new_value
        elif prop_name == 'unique_together':
            model_sig.apply_unique_together(self.new_value)
        elif prop_name == 'constraints':
            # Django >= 2.2
            constraint_sigs = []

            for constraint_data in self.new_value:
                constraint_attrs = constraint_data.copy()
                constraint_attrs.pop('name')
                constraint_attrs.pop('type')

                constraint_sigs.append(
                    ConstraintSignature(
                        name=constraint_data['name'],
                        constraint_type=constraint_data['type'],
                        attrs=constraint_attrs))

            model_sig.constraint_sigs = constraint_sigs
        elif prop_name == 'indexes':
            # Django >= 1.11
            index_sigs = []

            for index_data in self.new_value:
                index_attrs = index_data.copy()
                index_expressions = index_attrs.pop('expressions', None)
                index_name = index_attrs.pop('name', None)
                index_fields = index_attrs.pop('fields', None)

                index_sigs.append(
                    IndexSignature(attrs=index_attrs,
                                   expressions=index_expressions,
                                   fields=index_fields,
                                   name=index_name))

            model_sig.index_sigs = index_sigs
        else:
            simulation.fail('The property cannot be changed on a model.')

    def mutate(self, mutator, model):
        """Schedule a model meta property change on the mutator.

        This will instruct the mutator to change a meta property on a model. It
        will be scheduled and later executed on the database, if not optimized
        out.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.
        """
        mutator.change_meta(self, self.prop_name, self.new_value)

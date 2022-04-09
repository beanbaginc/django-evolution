"""Mutation that adds a field to a model.

Version Added:
    2.2
"""

from __future__ import unicode_literals

from functools import partial

from django.db import models

from django_evolution.compat import six
from django_evolution.mock_models import MockModel, MockRelated, create_field
from django_evolution.mutations.base import BaseModelFieldMutation
from django_evolution.signature import FieldSignature


class AddField(BaseModelFieldMutation):
    """A mutation that adds a field to a model.

    Version Changed:
        2.2:
        Moved into the :py:mod:`django_evolution.mutations.add_field` module.
    """

    simulation_failure_error = (
        'Cannot add the field "%(field_name)s" to model '
        '"%(app_label)s.%(model_name)s".'
    )

    def __init__(self, model_name, field_name, field_type, initial=None,
                 **field_attrs):
        """Initialize the mutation.

        Args:
            model_name (unicode):
                The name of the model to add the field to.

            field_name (unicode):
                The name of the new field.

            field_type (cls):
                The field class to use. This must be a subclass of
                :py:class:`django.db.models.Field`.

            initial (object, optional):
                The initial value for the field. This is required if non-null.

            **field_attrs (dict):
                Attributes to set on the field.
        """
        super(AddField, self).__init__(model_name, field_name)

        self.field_type = field_type
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
            self.serialize_attr(key, value)
            for key, value in six.iteritems(self.field_attrs)
        ]

        if self.initial is not None:
            params.append(self.serialize_attr('initial', self.initial))

        return [
            self.serialize_value(self.model_name),
            self.serialize_value(self.field_name),
            self.serialize_value(self.field_type),
        ] + sorted(params)

    def simulate(self, simulation):
        """Simulate the mutation.

        This will alter the database schema to add the specified field.

        Args:
            simulation (Simulation):
                The state for the simulation.

        Raises:
            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message.
        """
        model_sig = simulation.get_model_sig(self.model_name)

        if model_sig.get_field_sig(self.field_name) is not None:
            simulation.fail('A field with this name already exists.')

        if (not issubclass(self.field_type, models.ManyToManyField) and
            not self.field_attrs.get('null')
            and self.initial is None):
            simulation.fail('A non-null initial value must be specified in '
                            'the mutation.')

        field_attrs = self.field_attrs.copy()
        related_model = field_attrs.pop('related_model', None)

        field_sig = FieldSignature(field_name=self.field_name,
                                   field_type=self.field_type,
                                   field_attrs=field_attrs,
                                   related_model=related_model)
        model_sig.add_field_sig(field_sig)

    def mutate(self, mutator, model):
        """Schedule a field addition on the mutator.

        This will instruct the mutator to add a new field on a model. It will
        be scheduled and later executed on the database, if not optimized out.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.
        """
        if issubclass(self.field_type, models.ManyToManyField):
            self.add_m2m_table(mutator, model)
        else:
            self.add_column(mutator, model)

    def add_column(self, mutator, model):
        """Add a standard column to the model.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.
        """
        field = self._create_field(mutator, model)

        mutator.add_column(self, field, self.initial)

    def add_m2m_table(self, mutator, model):
        """Add a ManyToMany column to the model and an accompanying table.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.
        """
        field = self._create_field(mutator, model)

        related_app_label, related_model_name = \
            self.field_attrs['related_model'].split('.')
        related_sig = (
            mutator.project_sig
            .get_app_sig(related_app_label)
            .get_model_sig(related_model_name)
        )
        related_model = MockModel(project_sig=mutator.project_sig,
                                  app_name=related_app_label,
                                  model_name=related_model_name,
                                  model_sig=related_sig,
                                  db_name=mutator.database)
        related = MockRelated(related_model=related_model,
                              model=model,
                              field=field)

        if hasattr(field, '_get_m2m_column_name'):
            # Django < 1.2
            field.m2m_column_name = \
                partial(field._get_m2m_column_name, related)
            field.m2m_reverse_name = \
                partial(field._get_m2m_reverse_name, related)

            field.m2m_column_name = \
                partial(field._get_m2m_attr, related, 'column')
            field.m2m_reverse_name = \
                partial(field._get_m2m_reverse_attr, related, 'column')

        mutator.add_sql(self, mutator.evolver.add_m2m_table(model, field))

    def _create_field(self, mutator, parent_model):
        """Create a new field to add to the model.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            parent_model (django_evolution.mock_models.MockModel):
                The model to add the field to.

        Returns:
            django.db.models.Field:
            The newly-created field.
        """
        field_attrs = self.field_attrs.copy()
        related_model = field_attrs.pop('related_model', None)

        return create_field(project_sig=mutator.project_sig,
                            field_name=self.field_name,
                            field_type=self.field_type,
                            field_attrs=field_attrs,
                            parent_model=parent_model,
                            related_model=related_model)

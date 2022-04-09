"""Mutation that changes attributes on a field.

Version Added:
    2.2
"""

from __future__ import unicode_literals

from django.db import connections, models

from django_evolution.compat import six
from django_evolution.errors import EvolutionNotImplementedError
from django_evolution.mock_models import create_field
from django_evolution.mutations.base import BaseModelFieldMutation


class ChangeField(BaseModelFieldMutation):
    """A mutation that changes attributes on a field on a model.

    Version Changed:
        2.2:
        * Moved into the :py:mod:`django_evolution.mutations.change_field`
          module.

        * ``field_type`` can now be changed.
    """

    simulation_failure_error = (
        'Cannot change the field "%(field_name)s" on model '
        '"%(app_label)s.%(model_name)s".'
    )

    def __init__(self, model_name, field_name, field_type=None, initial=None,
                 **field_attrs):
        """Initialize the mutation.

        Args:
            model_name (unicode):
                The name of the model containing the field to change.

            field_name (unicode):
                The name of the field to change.

            field_type (type, optional):
                The new type of the field. This must be a subclass of
                :py:class:`~django.db.models.Field`.

                Version Added:
                    2.2

            initial (object, optional):
                The initial value for the field. This is required if non-null.

            **field_attrs (dict):
                Attributes to set on the field.
        """
        super(ChangeField, self).__init__(model_name, field_name)

        self.field_attrs = field_attrs
        self.field_type = field_type
        self.initial = initial

    def get_hint_params(self):
        """Return parameters for the mutation's hinted evolution.

        Returns:
            list of unicode:
            A list of parameter strings to pass to the mutation's constructor
            in a hinted evolution.
        """
        params = []

        if self.field_type is not None:
            params.append(self.serialize_attr('field_type', self.field_type))

        params += [
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

        field_type_changed, old_field, new_field = self._get_field_type_change(
            connection=connections[simulation.database],
            model=None,
            project_sig=simulation.project_sig,
            old_field_sig=field_sig)

        if self.field_type is not None:
            field_sig.field_type = self.field_type

        if field_type_changed:
            field_sig.field_attrs = self.field_attrs.copy()
        else:
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
        field_name = self.field_name
        field_sig = mutator.model_sig.get_field_sig(field_name)
        field = model._meta.get_field(field_name)

        if self.field_type is None:
            for attr_name in six.iterkeys(self.field_attrs):
                if attr_name not in mutator.evolver.supported_change_attrs:
                    raise EvolutionNotImplementedError(
                        "ChangeField does not support modifying the '%s' "
                        "attribute on '%s.%s'."
                        % (attr_name, self.model_name, field_name))

        field_type_changed, old_field, new_field = self._get_field_type_change(
            connection=connections[mutator.database],
            model=model,
            project_sig=mutator.project_sig,
            old_field_sig=field_sig)

        # Determine which attributes have changed in this mutation. If there
        # are changes, we'll apply them to the database.
        changed_field_attrs = self._get_changed_field_attrs(field_sig)

        if field_type_changed:
            mutator.change_column_type(mutation=self,
                                       old_field=field,
                                       new_field=new_field,
                                       new_attrs=changed_field_attrs)

            if mutator.evolver.change_column_type_sets_attrs:
                return

        if changed_field_attrs:
            mutator.change_column(mutation=self,
                                  field=field,
                                  new_attrs=changed_field_attrs)

    def _get_changed_field_attrs(self, old_field_sig):
        """Return the attributes that have changed.

        Version Added:
            2.2

        Args:
            old_field_sig (django_evolution.signature.FieldSignature):
                The signature of the old field, before any changes are
                applied.

        Returns:
            dict:
            A mapping of attribute names to a field change dictionary with
            the following keys:

            * ``old_value``: The value in the old field signature.
            * ``new_value``: The new value provided to the mutation.
        """
        changed_field_attrs = {}

        for attr_name, attr_value in six.iteritems(self.field_attrs):
            old_attr_value = old_field_sig.get_attr_value(attr_name)

            # Avoid useless SQL commands if nothing has changed.
            if old_attr_value != attr_value:
                changed_field_attrs[attr_name] = {
                    'old_value': old_attr_value,
                    'new_value': attr_value,
                }

        return changed_field_attrs

    def _get_field_type_change(self, connection, model, project_sig,
                               old_field_sig):
        """Return information on whether and how a field type has changed.

        Version Added:
            2.2

        Args:
            connection (django.db.backends.base.BaseDatabaseWrapper):
                The database connection where the mutation will occur.

            model (type):
                The model containing the field being changed.

            project_sig (django_evolution.signature.ProjectSignature):
                The project signature where the model and field signatures
                reside.

            old_field_sig (django_evolution.signature.FieldSignature):
                The signature of the old field.

        Returns:
            tuple:
            A 3-tuple containing:

            1. Whether the field type has changed.
            2. A field instance representing the old field, if the field
               type has changed.
            3. A field instance representing the new field, if the field
               type has changed.

            If the field type has not changed, this will be
            ``(False, None, None)``.
        """
        if (self.field_type is None or
            old_field_sig.field_type is self.field_type):
            return False, None, None

        # We'll need to create old and new fields in order to give the
        # mutators and database backend enough information on how to
        # transition from the old field to the new one.
        field_name = self.field_name

        old_field = create_field(project_sig=project_sig,
                                 field_name=field_name,
                                 field_type=old_field_sig.field_type,
                                 field_attrs=old_field_sig.field_attrs,
                                 related_model=old_field_sig.related_model,
                                 parent_model=model)

        new_field_attrs = self.field_attrs.copy()
        new_related_model = new_field_attrs.pop('related_model', None)

        new_field = create_field(project_sig=project_sig,
                                 field_name=field_name,
                                 field_type=self.field_type,
                                 field_attrs=new_field_attrs,
                                 related_model=new_related_model,
                                 parent_model=model)

        old_db_type = old_field.db_type(connection=connection)
        new_db_type = new_field.db_type(connection=connection)

        if old_db_type == new_db_type:
            return False, None, None

        return True, old_field, new_field

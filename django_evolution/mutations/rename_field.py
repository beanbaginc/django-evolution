"""Mutation that renames a field on a model.

Version Added:
    2.2
"""

from __future__ import unicode_literals

from django.db import models

from django_evolution.mock_models import MockModel, create_field
from django_evolution.mutations.base import BaseModelFieldMutation


class RenameField(BaseModelFieldMutation):
    """A mutation that renames a field on a model.

    Version Changed:
        2.2:
        Moved into the :py:mod:`django_evolution.mutations.rename_field`
        module.
    """

    simulation_failure_error = (
        'Cannot rename the field "%(field_name)s" on model '
        '"%(app_label)s.%(model_name)s".'
    )

    def __init__(self, model_name, old_field_name, new_field_name,
                 db_column=None, db_table=None):
        """Initialize the mutation.

        Args:
            model_name (unicode):
                The name of the model to add the field to.

            old_field_name (unicode):
                The old (existing) name of the field.

            new_field_name (unicode):
                The new name for the field.

            db_column (unicode, optional):
                The explicit column name to set for the field.

            db_table (object, optional):
                The explicit table name to use, if specifying a
                :py:class:`~django.db.models.ManyToManyField`.
        """
        super(RenameField, self).__init__(model_name, old_field_name)

        self.old_field_name = old_field_name
        self.new_field_name = new_field_name
        self.db_column = db_column
        self.db_table = db_table

    def get_hint_params(self):
        """Return parameters for the mutation's hinted evolution.

        Returns:
            list of unicode:
            A list of parameter strings to pass to the mutation's constructor
            in a hinted evolution.
        """
        params = [
            self.serialize_value(self.model_name),
            self.serialize_value(self.old_field_name),
            self.serialize_value(self.new_field_name),
        ]

        if self.db_column:
            params.append(self.serialize_attr('db_column', self.db_column))

        if self.db_table:
            params.append(self.serialize_attr('db_table', self.db_table))

        return params

    def simulate(self, simulation):
        """Simulate the mutation.

        This will alter the database schema to rename the specified field.

        Args:
            simulation (Simulation):
                The state for the simulation.

        Raises:
            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message.
        """
        model_sig = simulation.get_model_sig(self.model_name)

        field_sig = simulation.get_field_sig(self.model_name,
                                             self.old_field_name).clone()
        field_sig.field_name = self.new_field_name

        if issubclass(field_sig.field_type, models.ManyToManyField):
            if self.db_table:
                field_sig.field_attrs['db_table'] = self.db_table
            else:
                field_sig.field_attrs.pop('db_table', None)
        elif self.db_column:
            field_sig.field_attrs['db_column'] = self.db_column
        else:
            # db_column and db_table were not specified (or not specified for
            # the appropriate field types). Clear the old value if one was set.
            # This amounts to resetting the column or table name to the Django
            # default name
            field_sig.field_attrs.pop('db_column', None)

        model_sig.remove_field_sig(self.old_field_name)
        model_sig.add_field_sig(field_sig)

    def mutate(self, mutator, model):
        """Schedule a field rename on the mutator.

        This will instruct the mutator to rename a field on a model. It will be
        scheduled and later executed on the database, if not optimized out.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.
        """
        old_field_sig = mutator.model_sig.get_field_sig(self.old_field_name)
        field_type = old_field_sig.field_type

        # Duplicate the old field sig, and apply the table/column changes.
        new_field_sig = old_field_sig.clone()

        if issubclass(old_field_sig.field_type, models.ManyToManyField):
            if self.db_table:
                new_field_sig.field_attrs['db_table'] = self.db_table
            else:
                new_field_sig.field_attrs.pop('db_table', None)
        elif self.db_column:
            new_field_sig.field_attrs['db_column'] = self.db_column
        else:
            new_field_sig.field_attrs.pop('db_column', None)

        # Create the mock field instances.
        new_model = MockModel(project_sig=mutator.project_sig,
                              app_name=mutator.app_label,
                              model_name=self.model_name,
                              model_sig=mutator.model_sig,
                              db_name=mutator.database)

        old_field = create_field(project_sig=mutator.project_sig,
                                 field_name=self.old_field_name,
                                 field_type=field_type,
                                 field_attrs=old_field_sig.field_attrs,
                                 related_model=old_field_sig.related_model,
                                 parent_model=new_model)
        new_field = create_field(project_sig=mutator.project_sig,
                                 field_name=self.new_field_name,
                                 field_type=field_type,
                                 field_attrs=new_field_sig.field_attrs,
                                 related_model=new_field_sig.related_model,
                                 parent_model=new_model)

        evolver = mutator.evolver

        if issubclass(field_type, models.ManyToManyField):
            old_m2m_table = old_field._get_m2m_db_table(new_model._meta)
            new_m2m_table = new_field._get_m2m_db_table(new_model._meta)

            sql = evolver.rename_table(new_model, old_m2m_table, new_m2m_table)
        else:
            sql = evolver.rename_column(new_model, old_field, new_field)

        mutator.add_sql(self, sql)

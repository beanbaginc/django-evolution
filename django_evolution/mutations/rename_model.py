"""Mutation that renames a model.

Version Added:
    2.2
"""

from __future__ import unicode_literals

from django_evolution.mock_models import MockModel
from django_evolution.mutations.base import BaseModelMutation


class RenameModel(BaseModelMutation):
    """A mutation that renames a model.

    Version Changed:
        2.2:
        Moved into the :py:mod:`django_evolution.mutations.rename_model`
        module.
    """

    simulation_failure_error = \
        'Cannot rename the model "%(app_label)s.%(model_name)s".'

    def __init__(self, old_model_name, new_model_name, db_table):
        """Initialize the mutation.

        Args:
            old_model_name (unicode):
                The old (existing) name of the model to rename.

            new_model_name (unicode):
                The new name for the model.

            db_table (unicode):
                The table name in the database for this model.
        """
        super(RenameModel, self).__init__(old_model_name)

        self.old_model_name = old_model_name
        self.new_model_name = new_model_name
        self.db_table = db_table

    def get_hint_params(self):
        """Return parameters for the mutation's hinted evolution.

        Returns:
            list of unicode:
            A list of parameter strings to pass to the mutation's constructor
            in a hinted evolution.
        """
        params = [
            self.serialize_value(self.old_model_name),
            self.serialize_value(self.new_model_name),
        ]

        if self.db_table:
            params.append(self.serialize_attr('db_table', self.db_table)),

        return params

    def simulate(self, simulation):
        """Simulate the mutation.

        This will alter the database schema to rename the specified model.

        Args:
            simulation (Simulation):
                The state for the simulation.

        Raises:
            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message.
        """
        app_sig = simulation.get_app_sig()

        model_sig = simulation.get_model_sig(self.old_model_name).clone()
        model_sig.model_name = self.new_model_name
        model_sig.table_name = self.db_table

        app_sig.remove_model_sig(self.old_model_name)
        app_sig.add_model_sig(model_sig)

        old_related_model = '%s.%s' % (simulation.app_label,
                                       self.old_model_name)
        new_related_model = '%s.%s' % (simulation.app_label,
                                       self.new_model_name)

        for cur_app_sig in simulation.project_sig.app_sigs:
            for cur_model_sig in cur_app_sig.model_sigs:
                for cur_field_sig in cur_model_sig.field_sigs:
                    if cur_field_sig.related_model == old_related_model:
                        cur_field_sig.related_model = new_related_model

    def mutate(self, mutator, model):
        """Schedule a model rename on the mutator.

        This will instruct the mutator to rename a model. It will be scheduled
        and later executed on the database, if not optimized out.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.
        """
        old_model_sig = mutator.model_sig

        new_model_sig = old_model_sig.clone()
        new_model_sig.model_name = self.new_model_name
        new_model_sig.table_name = self.db_table

        new_model = MockModel(project_sig=mutator.project_sig,
                              app_name=mutator.app_label,
                              model_name=self.new_model_name,
                              model_sig=new_model_sig,
                              db_name=mutator.database)

        mutator.add_sql(
            self,
            mutator.evolver.rename_table(new_model,
                                         old_model_sig.table_name,
                                         new_model_sig.table_name))

import copy

from django_evolution.db import EvolutionOperationsMulti
from django_evolution.errors import CannotSimulate
from django_evolution.mutations import MockModel, MutateModelField
from django_evolution.utils import get_database_for_model_name


class ModelMutator(object):
    """Tracks and runs mutations for a model.

    A ModelMutator is bound to a particular model (by type, not instance) and
    handles operations that apply to that model.

    Operations are first registered by mutations, and then later provided to
    the database's operations backend, where they will be applied to the
    database.

    After all operations are added, the caller is expected to call to_sql()
    to get the SQL statements needed to apply those operations. Once called,
    the mutator is finalized, and new operations cannot be added.

    ModelMutator only works with mutations that are instances of
    MutateModelField. It is also intended for internal use by AppMutator.
    """
    def __init__(self, app_mutator, model_name, app_label, proj_sig,
                 database_sig, database):
        self.app_mutator = app_mutator
        self.model_name = model_name
        self.app_label = app_label
        self.database = (database or
                         get_database_for_model_name(app_label, model_name))
        self.can_simulate = True
        self._ops = []
        self._finalized = False

        assert self.database
        evolution_ops = EvolutionOperationsMulti(self.database,
                                                 self.database_sig)
        self.evolver = evolution_ops.get_evolver()

    @property
    def proj_sig(self):
        return self.app_mutator.proj_sig

    @property
    def database_sig(self):
        return self.app_mutator.database_sig

    @property
    def model_sig(self):
        return self.proj_sig[self.app_label][self.model_name]

    def create_model(self):
        """Creates a mock model instance with the stored information.

        This is typically used when calling a mutation's mutate() function
        and passing a model instance, but can also be called whenever
        a new instance of the model is needed for any lookups.
        """
        return MockModel(self.proj_sig, self.app_label, self.model_name,
                         self.model_sig, db_name=self.database)

    def add_column(self, mutation, field, initial):
        """Adds a pending Add Column operation.

        This will cause to_sql() to include SQL for adding the column
        with the given information to the model.
        """
        assert not self._finalized

        self._ops.append({
            'type': 'add_column',
            'mutation': mutation,
            'field': field,
            'initial': initial,
        })

    def change_column(self, mutation, field, attr_name, old_value, new_value):
        """Adds a pending Change Column operation.

        This will cause to_sql() to include SQL for changing an attribute
        for the given column.
        """
        assert not self._finalized

        self._ops.append({
            'type': 'change_column',
            'mutation': mutation,
            'field': field,
            'attr_name': attr_name,
            'old_value': old_value,
            'new_value': new_value,
        })

    def delete_column(self, mutation, field):
        """Adds a pending Delete Column operation.

        This will cause to_sql() to include SQL for deleting the given
        column.
        """
        assert not self._finalized

        self._ops.append({
            'type': 'delete_column',
            'mutation': mutation,
            'field': field,
        })

    def delete_model(self, mutation):
        """Adds a pending Delete Model operation.

        This will cause to_sql() to include SQL for deleting the model.
        """
        assert not self._finalized

        self._ops.append({
            'type': 'delete_model',
            'mutation': mutation,
        })

    def change_meta(self, mutation, prop_name, new_value):
        """Adds a pending Change Meta operation.

        This will cause to_sql() to include SQL for changing a supported
        attribute in the model's Meta class.
        """
        assert not self._finalized

        self._ops.append({
            'type': 'change_meta',
            'mutation': mutation,
            'prop_name': prop_name,
            'old_value': self.model_sig['meta'][prop_name],
            'new_value': new_value,
        })

    def add_sql(self, mutation, sql):
        """Adds an operation for executing custom SQL.

        This will cause to_sql() to include the provided SQL statements.
        The SQL should be a list of a statements.
        """
        assert not self._finalized

        self._ops.append({
            'type': 'sql',
            'mutation': mutation,
            'sql': sql,
        })

    def run_mutation(self, mutation):
        """Runs the specified mutation.

        The mutation will be provided with a temporary mock instance of a
        model that can be used for field or meta lookups.

        The mutation must be an instance of MutateModelField.
        """
        assert isinstance(mutation, MutateModelField)
        assert not self._finalized

        mutation.mutate(self, self.create_model())
        self.run_simulation(mutation)

    def run_simulation(self, mutation):
        try:
            mutation.simulate(self.app_label, self.proj_sig,
                              self.database_sig, self.database)
        except CannotSimulate:
            self.can_simulate = False

    def to_sql(self):
        """Returns SQL for the operations added to this mutator.

        The SQL will represent all the operations made by the mutator,
        as determined by the database operations backend.

        Once called, no new operations can be added to the mutator.
        """
        assert not self._finalized

        self._finalized = True

        return self.evolver.generate_table_ops_sql(self, self._ops)

    def finish_op(self, op):
        """Finishes handling an operation.

        This is called by the evolution operations backend when it is done
        with an operation.

        Simulations for the operation's associated mutation will be applied,
        in order to update the signatures for the changes made by the
        mutation.
        """
        mutation = op['mutation']

        try:
            mutation.simulate(self.app_label, self.proj_sig,
                              self.database_sig, self.database)
        except CannotSimulate:
            self.can_simulate = False


class SQLMutator(object):
    def __init__(self, mutation, sql):
        self.mutation = mutation
        self.sql = sql

    def to_sql(self):
        return self.sql


class AppMutator(object):
    """Tracks and runs mutations for an app.

    An AppMutator is bound to a particular app name, and handles operations
    that apply to anything on that app.

    This will create a ModelMutator internally for each set of adjacent
    operations that apply to the same model, allowing the database operations
    backend to optimize those operations. This means that it's in the best
    interest of a developer to keep related mutations batched together as much
    as possible.

    After all operations are added, the caller is expected to call to_sql()
    to get the SQL statements needed to apply those operations. Once called,
    the mutator is finalized, and new operations cannot be added.
    """
    def __init__(self, app_label, proj_sig, database_sig, database=None):
        self.app_label = app_label
        self.proj_sig = proj_sig
        self.database_sig = database_sig
        self.database = database
        self.can_simulate = True
        self._last_model_mutator = None
        self._mutators = []
        self._finalized = False
        self._orig_proj_sig = copy.deepcopy(self.proj_sig)
        self._orig_database_sig = copy.deepcopy(self.database_sig)

    def run_mutation(self, mutation):
        """Runs a mutation that applies to this app.

        If the mutation applies to a model, a ModelMutator for that model
        will be given the job of running this mutation. If the prior operation
        operated on the same model, then the previously created ModelMutator
        will be used. Otherwise, a new one will be created.
        """
        if isinstance(mutation, MutateModelField):
            if (self._last_model_mutator and
                mutation.model_name == self._last_model_mutator.model_name):
                # We can continue to apply operations to the previous
                # ModelMutator.
                model_mutator = self._last_model_mutator
            else:
                # This is a new model. Begin a new ModelMutator for it.
                self._finalize_model_mutator()

                model_mutator = ModelMutator(
                    self, mutation.model_name, self.app_label, self.proj_sig,
                    self.database_sig, self.database)
                self._last_model_mutator = model_mutator

            model_mutator.run_mutation(mutation)
        else:
            self._finalize_model_mutator()

            mutation.mutate(self)

    def run_mutations(self, mutations):
        """Runs a list of mutations."""
        for mutation in mutations:
            self.run_mutation(mutation)

    def add_sql(self, mutation, sql):
        """Adds SQL that applies to the application."""
        assert not self._last_model_mutator

        self._mutators.append(SQLMutator(mutation, sql))

    def to_sql(self):
        """Returns SQL for the operations added to this mutator.

        The SQL will represent all the operations made by the mutator.
        Once called, no new operations can be added.
        """
        assert not self._finalized

        # Finalize one last time.
        self._finalize_model_mutator()

        self.proj_sig = self._orig_proj_sig
        self.database_sig = self._orig_database_sig

        sql = []

        for mutator in self._mutators:
            sql.extend(mutator.to_sql())

        self._finalized = True

        return sql

    def _finalize_model_mutator(self):
        """Finalizes the current ModelMutator, if one exists.

        The ModelMutator's SQL will be generated and added to the resulting
        SQL for this AppMutator.
        """
        if self._last_model_mutator:
            if not self._last_model_mutator.can_simulate:
                self.can_simulate = False

            self._mutators.append(self._last_model_mutator)
            self._last_model_mutator = None

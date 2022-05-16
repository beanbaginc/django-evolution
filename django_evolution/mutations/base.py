"""Base support for mutations.

Version Added:
    2.2
"""

from __future__ import unicode_literals

from django.db.utils import DEFAULT_DB_ALIAS

from django_evolution.compat import six
from django_evolution.db import EvolutionOperationsMulti
from django_evolution.db.state import DatabaseState
from django_evolution.errors import SimulationFailure
from django_evolution.serialization import serialize_to_python
from django_evolution.signature import ProjectSignature
from django_evolution.utils.models import get_database_for_model_name


class Simulation(object):
    """State for a database mutation simulation.

    This provides state and utility functions for simulating a mutation on
    a database signature. This is provided to :py:meth:`BaseMutation.simulate`
    functions, given them access to all simulation state and a consistent way
    of failing simulations.

    Version Changed:
        2.2:
        Moved into the :py:mod:`django_evolution.mutations.base` module.
    """

    def __init__(self, mutation, app_label, project_sig, database_state,
                 legacy_app_label=None, database=DEFAULT_DB_ALIAS):
        """Initialize the simulation state.

        Args:
            mutation (BaseMutation):
                The mutation this simulation applies to.

            app_label (unicode):
                The name of the application this simulation applies to.

            project_sig (dict):
                The project signature for the simulation to look up and
                modify.

            database_state (django_evolution.db.state.DatabaseState):
                The database state for the simulation to look up and modify.

            legacy_app_label (unicode, optional):
                The legacy label of the app this simulation applies to.
                This is based on the module name and is used in the
                transitioning of pre-Django 1.7 signatures.

            database (unicode, optional):
                The registered database name in Django to simulate operating
                on.
        """
        assert isinstance(project_sig, ProjectSignature), \
               'project_sig must be a ProjectSignature instance'
        assert (database_state is None or
                isinstance(database_state, DatabaseState)), \
               'database_state must be None or a DatabaseState instance'

        self.mutation = mutation
        self.app_label = app_label
        self.legacy_app_label = legacy_app_label or app_label
        self.project_sig = project_sig
        self.database_state = database_state
        self.database = database

    def get_evolver(self):
        """Return an evolver for the database.

        Returns:
            django_evolution.db.EvolutionOperationsMulti:
            The database evolver for this type of database.
        """
        return EvolutionOperationsMulti(self.database,
                                        self.database_state).get_evolver()

    def get_app_sig(self):
        """Return the current application signature.

        Returns:
            dict:
            The application signature.

        Returns:
            django_evolution.signature.AppSignature:
            The signature for the app.

        Raises:
            django_evolution.errors.SimulationFailure:
                A signature could not be found for the application.
        """
        app_sig = self.project_sig.get_app_sig(self.app_label)

        if (app_sig is None and
            self.legacy_app_label is not None and
            self.legacy_app_label != self.app_label):
            # Check if it can be found by the legacy label.
            app_sig = self.project_sig.get_app_sig(self.legacy_app_label)

        if app_sig:
            return app_sig

        self.fail('The application could not be found in the signature.')

    def get_model_sig(self, model_name):
        """Return the signature for a model with the given name.

        Args:
            model_name (unicode):
                The name of the model to fetch a signature for.

        Returns:
            django_evolution.signature.ModelSignature:
            The signature for the model.

        Raises:
            django_evolution.errors.SimulationFailure:
                A signature could not be found for the model or its parent
                application.
        """
        model_sig = self.get_app_sig().get_model_sig(model_name)

        if model_sig:
            return model_sig

        self.fail('The model could not be found in the signature.',
                  model_name=model_name)

    def get_field_sig(self, model_name, field_name):
        """Return the signature for a field with the given name.

        Args:
            model_name (unicode):
                The name of the model containing the field.

            field_name (unicode):
                The name of the field to fetch a signature for.

        Returns:
            django_evolution.signature.FieldSignature:
            The signature for the field.

        Raises:
            django_evolution.errors.SimulationFailure:
                A signature could not be found for the field, its parent
                model, or its parent application.
        """
        field_sig = self.get_model_sig(model_name).get_field_sig(field_name)

        if field_sig:
            return field_sig

        self.fail('The field could not be found in the signature.',
                  model_name=model_name,
                  field_name=field_name)

    def fail(self, error, **error_vars):
        """Fail the simulation.

        This will end up raising a
        :py:class:`~django_evolution.errors.SimulationFailure` with an error
        message based on the mutation's simulation failed message an the
        provided message.

        Args:
            error (unicode):
                The error message for this particular failure.

            **error_vars (dict):
                Variables to include in the error message. These will
                override any defaults for the mutation's error.

        Raises:
            django_evolution.errors.SimulationFailure:
                The resulting simulation failure with the given error.
        """
        msg = '%s %s' % (self.mutation.simulation_failure_error, error)

        error_dict = {
            'app_label': self.app_label,
        }
        error_dict.update(
            (key, getattr(self.mutation, value))
            for key, value in six.iteritems(self.mutation.error_vars)
        )
        error_dict.update(error_vars)

        raise SimulationFailure(msg % error_dict)


class BaseMutation(object):
    """Base class for a schema mutation.

    These are responsible for simulating schema mutations and applying actual
    mutations to a database signature.

    Version Changed:
        2.2:
        Moved into the :py:mod:`django_evolution.mutations.base` module.
    """

    simulation_failure_error = 'Cannot simulate the mutation.'
    error_vars = {}

    def generate_hint(self):
        """Return a hinted evolution for the mutation.

        This will generate a line that will be used in a hinted evolution
        file. This method generally should not be overridden. Instead, use
        :py:meth:`get_hint_params`.

        Returns:
            unicode:
            A hinted evolution statement for this mutation.
        """
        return '%s(%s)' % (self.__class__.__name__,
                           ', '.join(self.get_hint_params()))

    def get_hint_params(self):
        """Return parameters for the mutation's hinted evolution.

        Returns:
            list of unicode:
            A list of parameter strings to pass to the mutation's constructor
            in a hinted evolution.
        """
        return []

    def generate_dependencies(self, app_label, **kwargs):
        """Return automatic dependencies for the parent evolution.

        This allows a mutation to affect the order in which the parent
        evolution is applied, relative to other evolutions or migrations.

        Version Added:
            2.1

        Args:
            app_label (unicode):
                The label of the app containing this mutation.

            **kwargs (dict):
                Additional keyword arguments, for future use.

        Returns:
            dict:
            A dictionary of dependencies. This may have zero or more of the
            following keys:

            * ``before_migrations``
            * ``after_migrations``
            * ``before_evolutions``
            * ``after_evolutions``
        """
        return {}

    def run_simulation(self, **kwargs):
        """Run a simulation for a mutation.

        This will prepare and execute a simulation on this mutation,
        constructing a :py:class:`Simulation` and passing it to
        :py:meth:`simulate`. The simulation will apply a mutation on the
        provided database signature, modifying it to match the state described
        to the mutation. This allows Django Evolution to test evolutions before
        they hit the database.

        Args:
            simulation (Simulation):
                The state for the simulation.

        Raises:
            django_evolution.errors.CannotSimulate:
                The simulation cannot be executed for this mutation. The
                reason is in the exception's message.

            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message.
        """
        self.simulate(Simulation(self, **kwargs))

    def simulate(self, simulation):
        """Perform a simulation of a mutation.

        This will attempt to perform a mutation on the database signature,
        modifying it to match the state described to the mutation. This allows
        Django Evolution to test evolutions before they hit the database.

        Args:
            simulation (Simulation):
                The state for the simulation.

        Raises:
            django_evolution.errors.CannotSimulate:
                The simulation cannot be executed for this mutation. The
                reason is in the exception's message.

            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message.
        """
        raise NotImplementedError

    def mutate(self, mutator):
        """Schedule a database mutation on the mutator.

        This will instruct the mutator to perform one or more database
        mutations for an app. Those will be scheduled and later executed on the
        database, if not optimized out.

        Args:
            mutator (django_evolution.mutators.AppMutator):
                The mutator to perform an operation on.

        Raises:
            django_evolution.errors.EvolutionNotImplementedError:
                The configured mutation is not supported on this type of
                database.
        """
        raise NotImplementedError

    def is_mutable(self, app_label, project_sig, database_state, database):
        """Return whether the mutation can be applied to the database.

        This should check if the database or parts of the signature matches
        the attributes provided to the mutation.

        Args:
            app_label (unicode):
                The label for the Django application to be mutated.

            project_sig (dict):
                The project's schema signature.

            database_state (django_evolution.db.state.DatabaseState):
                The database's schema signature.

            database (unicode):
                The name of the database the operation would be performed on.

        Returns:
            bool:
            ``True`` if the mutation can run. ``False`` if it cannot.
        """
        return False

    def serialize_value(self, value):
        """Serialize a value for use in a mutation statement.

        This will attempt to represent the value as something Python can
        execute, across Python versions. The string representation of the
        value is used by default.

        See :py:func:`django_evolution.serialization.serialize_to_python`
        for details.

        Args:
            value (object):
                The value to serialize.

        Returns:
            unicode:
            The serialized string.
        """
        return serialize_to_python(value)

    def serialize_attr(self, attr_name, attr_value):
        """Serialize an attribute for use in a mutation statement.

        This will create a ``name=value`` string, with the value serialized
        using :py:meth:`serialize_value`.

        Args:
            attr_name (unicode):
                The attribute's name.

            attr_value (object):
                The attribute's value.

        Returns:
            unicode:
            The serialized attribute string.
        """
        return '%s=%s' % (attr_name, self.serialize_value(attr_value))

    def __hash__(self):
        """Return a hash of this mutation.

        Returns:
            int:
            The mutation's hash.
        """
        return id(self)

    def __eq__(self, other):
        """Return whether this mutation equals another.

        Two mutations are equal if they're of the same type and generate
        the same hinted evolution.

        Args:
            other (BaseMutation):
                The mutation to compare against.

        Returns:
            bool:
            ``True`` if the mutations are equal. ``False`` if they are not.
        """
        return (type(self) is type(other) and
                self.generate_hint() == other.generate_hint())

    def __str__(self):
        """Return a hinted evolution for the mutation.

        Returns:
            unicode:
            The hinted evolution.
        """
        return self.generate_hint()

    def __repr__(self):
        """Return a string representation of the mutation.

        Returns:
            unicode:
            A string representation of the mutation.
        """
        return '<%s>' % self


class BaseUpgradeMethodMutation(BaseMutation):
    """Base class for a mutation that changes an app's upgrade method.

    Version Added:
        2.2
    """

    def is_mutable(self, *args, **kwargs):
        """Return whether the mutation can be applied to the database.

        Args:
            *args (tuple, unused):
                Unused positional arguments.

            **kwargs (tuple, unused):
                Unused positional arguments.

        Returns:
            bool:
            ``True``, always.
        """
        return True

    def generate_dependencies(self, app_label, **kwargs):
        """Return automatic dependencies for the parent evolution.

        This allows a mutation to affect the order in which the parent
        evolution is applied, relative to other evolutions or migrations.

        This must be implemented by subclasses.

        Args:
            app_label (unicode):
                The label of the app containing this mutation.

            **kwargs (dict):
                Additional keyword arguments, for future use.

        Returns:
            dict:
            A dictionary of dependencies. This may have zero or more of the
            following keys:

            * ``before_migrations``
            * ``after_migrations``
            * ``before_evolutions``
            * ``after_evolutions``
        """
        raise NotImplementedError

    def mutate(self, mutator):
        """Schedule an app mutation on the mutator.

        As this mutation just modifies state on the signature, no actual
        database operations are performed. By default, this does nothing.

        Args:
            mutator (django_evolution.mutators.AppMutator, unused):
                The mutator to perform an operation on.
        """
        pass


class BaseModelMutation(BaseMutation):
    """Base class for a mutation affecting a single model.

    Version Changed:
        2.2:
        Moved into the :py:mod:`django_evolution.mutations.base` module.
    """

    error_vars = dict({
        'model_name': 'model_name',
    }, **BaseMutation.error_vars)

    def __init__(self, model_name):
        """Initialize the mutation.

        Args:
            model_name (unicode):
                The name of the model being mutated.
        """
        super(BaseModelMutation, self).__init__()

        self.model_name = model_name

    def evolver(self, model, database_state, database=None):
        if database is None:
            database = get_database_for_model_name(model.app_label,
                                                   model.model_name)

        return EvolutionOperationsMulti(database, database_state).get_evolver()

    def mutate(self, mutator, model):
        """Schedule a model mutation on the mutator.

        This will instruct the mutator to perform one or more database
        mutations for a model. Those will be scheduled and later executed on
        the database, if not optimized out.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.

        Raises:
            django_evolution.errors.EvolutionNotImplementedError:
                The configured mutation is not supported on this type of
                database.
        """
        raise NotImplementedError

    def is_mutable(self, app_label, project_sig, database_state, database):
        """Return whether the mutation can be applied to the database.

        This will if the database matches that of the model.

        Args:
            app_label (unicode):
                The label for the Django application to be mutated.

            project_sig (dict, unused):
                The project's schema signature.

            database_state (django_evolution.db.state.DatabaseState, unused):
                The database state.

            database (unicode):
                The name of the database the operation would be performed on.

        Returns:
            bool:
            ``True`` if the mutation can run. ``False`` if it cannot.
        """
        db_name = (database or
                   get_database_for_model_name(app_label, self.model_name))
        return db_name and db_name == database


class BaseModelFieldMutation(BaseModelMutation):
    """Base class for any fields that mutate a model.

    This is used for classes that perform any mutation on a model. Such
    mutations will be provided a model they can work with.

    Operations added to the mutator by this field will be associated with that
    model. That will allow the operations backend to perform any optimizations
    to improve evolution time for the model.

    Version Changed:
        2.2:
        Moved into the :py:mod:`django_evolution.mutations.base` module.
    """

    error_vars = dict({
        'field_name': 'field_name',
    }, **BaseModelMutation.error_vars)

    def __init__(self, model_name, field_name):
        """Initialize the mutation.

        Args:
            model_name (unicode):
                The name of the model containing the field.

            field_name (unicode):
                The name of the field to mutate.
        """
        super(BaseModelFieldMutation, self).__init__(model_name)

        self.field_name = field_name

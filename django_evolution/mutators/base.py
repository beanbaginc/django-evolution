"""Base classes for mutators.

Version Added:
    2.2
"""

from __future__ import unicode_literals

from django_evolution.errors import CannotSimulate


class BaseMutator(object):
    """Base class for all mutators.

    Version Added:
        2.2
    """

    def __init__(self):
        """Initialize the mutator."""
        self.can_simulate = True
        self.finalized = False

    def finalize(self):
        """Finalize the mutator.

        After a mutator is finalized, no new state can be scheduled or
        modified.
        """
        self.finalized = True

    def to_sql(self):
        """Return SQL for the operations added to this mutator.

        The SQL will represent all the operations made by the mutator, as
        determined by the database operations backend.

        Subclasses that override this must call :py:meth:`finalize` when done.

        Returns:
            list:
            The list of SQL statements.

            Each item may be one of the following:

            1. A Unicode string representing an SQL statement
            2. A tuple in the form of ``(sql_statement, sql_params)``
            3. An instance of :py:class:`django_evolution.db.sql_result.
               SQLResult`.
        """
        return []


class BaseAppStateMutator(BaseMutator):
    """Base class for mutators that modify app state.

    These will always be constructed and managed by
    :py:class:`django_evolution.mutators.app_mutator.AppMutator`.

    Version Added:
        2.2
    """

    def __init__(self, app_mutator):
        """Initialize the mutator.

        Args:
            app_mutator (django_evolution.mutators.app_mutator.AppMutator):
                The parent app mutator.
        """
        super(BaseAppStateMutator, self).__init__()

        self.app_mutator = app_mutator
        self.database = app_mutator.database

    @property
    def app_label(self):
        """The app label representing the app being changed.

        This always forwards on to the parent app mutator's app label, as that
        may change.

        Type:
            unicode
        """
        return self.app_mutator.app_label

    @app_label.setter
    def app_label(self, value):
        """Set the app label representing the app being changed.

        This always updates the parent app mutator's app label.

        Args:
            value (unicode):
                The new app label.
        """
        self.app_mutator.app_label = value

    @property
    def legacy_app_label(self):
        """The legacy app label representing the app being changed.

        This always forwards on to the parent app mutator's legacy app label,
        as that may change.

        Type:
            unicode
        """
        return self.app_mutator.legacy_app_label

    @property
    def project_sig(self):
        """The project signature being used for operations.

        This always forwards on to the parent app mutator's project signature,
        as that may change.

        Type:
            django_evolution.signature.ProjectSignature
        """
        return self.app_mutator.project_sig

    @property
    def database_state(self):
        """The database state being used for operations.

        This always forwards on to the parent app mutator's databaes state,
        as that may change.

        Type:
            django_evolution.db.state.DatabaseState
        """
        return self.app_mutator.database_state

    def run_mutation(self, mutation, mutate_kwargs={}):
        """Run the specified mutation.

        The mutation may apply changes to the database.

        Args:
            mutation (django_evolution.mutations.BaseMutation):
                The mutation to run.

            mutate_kwargs (dict, optional):
                Keyword arguments to pass to the mutate method.

        Raises:
            django_evolution.errors.EvolutionBaselineMissingError:
                The model signature or parent app signature could not be found.
        """
        assert not self.finalized

        mutation.mutate(self, **mutate_kwargs)
        self.run_simulation(mutation)

    def run_simulation(self, mutation):
        """Run a simulation of a mutation.

        The mutation may apply changes to the database project signature, but
        may not apply to the database.

        This may be run after :py:meth:`run_mutation`, in order to update the
        signature with the changes that a mutation has made.

        If simulation fails, :py:attr:`can_simulate` will be set to ``False``.

        Args:
            mutation (django_evolution.mutations.BaseMutation):
                The mutation to simulate.
        """
        try:
            mutation.run_simulation(app_label=self.app_label,
                                    legacy_app_label=self.legacy_app_label,
                                    project_sig=self.project_sig,
                                    database_state=self.database_state,
                                    database=self.database)
        except CannotSimulate:
            self.can_simulate = False

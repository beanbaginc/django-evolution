"""Standard exceptions for Django Evolution."""

from __future__ import unicode_literals

from django_evolution.compat import six


class EvolutionException(Exception):
    """Base class for a Django Evolution exception."""

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return str(self.msg)


class EvolutionExecutionError(EvolutionException):
    """Execution of an evolution failed.

    Details about the failure, including the app that failed and the last
    SQL statement executed, are available in the exception as attributes.

    Attributes:
        app_label (unicode):
            The label of the app that failed evolution. This may be ``None``.

        detailed_error (unicode):
            Detailed error information from the failure that triggered this
            exception. This might be another exception's error message, or
            it may be ``None``.

        last_sql_statement (unicode):
            The last SQL statement that was executed. This may be ``None``.
    """

    def __init__(self, msg, app_label=None, detailed_error=None,
                 last_sql_statement=None):
        """Initialize the error.

        Args:
            msg (unicode):
                The error message.

            app_label (unicode, optional):
                The label of the app that failed evolution.

            detailed_error (unicode, optional):
                Detailed error information from the failure that triggered this
                exception. This might be another exception's error message.

            last_sql_statement (unicode, optional):
                The last SQL statement that was executed.
        """
        super(EvolutionExecutionError, self).__init__(msg)

        self.app_label = app_label
        self.detailed_error = detailed_error
        self.last_sql_statement = last_sql_statement


class CannotSimulate(EvolutionException):
    """A mutation cannot be simulated."""


class SimulationFailure(EvolutionException):
    """A mutation simulation has failed."""


class EvolutionNotImplementedError(EvolutionException, NotImplementedError):
    """An operation is not supported by the mutation or database backend."""


class DatabaseStateError(EvolutionException):
    """There was an issue working with database state."""


class MissingSignatureError(EvolutionException):
    """A requested signature could not be found."""


class QueueEvolverTaskError(EvolutionException):
    """Error queueing an evolver task."""


class EvolutionTaskAlreadyQueuedError(QueueEvolverTaskError):
    """The task has already been queued on the evolver."""


class EvolutionBaselineMissingError(EvolutionException):
    """An evolution baseline is missing."""


class InvalidSignatureVersion(EvolutionException):
    """An invalid signature version was provided or found."""

    def __init__(self, version):
        """Initialize the exception.

        Args:
            version (int):
                The invalid signature version.
        """
        super(InvalidSignatureVersion, self).__init__(
            '%s is not a known signature version' % version)


class BaseMigrationError(EvolutionException):
    """Base class for migration errors."""


class MigrationHistoryError(BaseMigrationError):
    """An error with the stored history of migrations.

    This is raised if any applied migrations have unapplied dependencies.
    """


class MigrationConflictsError(BaseMigrationError):
    """There are conflicts between migrations."""

    def __init__(self, conflicts):
        """Initialize the error.

        Args:
            conflicts (dict):
                A dictionary of conflicts, provided by the migrations system.
        """
        # Note that we're using the same error message that Django's migrate
        # command uses.
        super(MigrationConflictsError, self).__init__(
            "Conflicting migrations detected; multiple leaf nodes "
            "in the migration graph: (%s).\n"
            "To fix them run 'python manage.py makemigrations "
            "--merge'"
            % '; '.join(
                '%s in %s' % (', '.join(sorted(conflict_names)), app_label)
                for app_label, conflict_names in six.iteritems(conflicts)
            ))


class DjangoEvolutionSupportError(EvolutionException):
    """A feature isn't supported by the current version of Django."""

"""Task for purging an application.

Version Added:
    2.2:
    This was previously located in :py:mod:`django_evolution.evolve`.
"""

from __future__ import unicode_literals

from django_evolution.compat import six
from django_evolution.compat.translation import gettext as _
from django_evolution.errors import EvolutionExecutionError
from django_evolution.evolve.base import BaseEvolutionTask
from django_evolution.mutations import DeleteApplication
from django_evolution.mutators import AppMutator


class PurgeAppTask(BaseEvolutionTask):
    """A task for purging an application's tables from the database.

    Attributes:
        app_label (unicode):
            The app label for the app to purge.
    """

    def __init__(self, evolver, app_label):
        """Initialize the task.

        Args:
            evolver (Evolver):
                The evolver that will execute the task.

            app_label (unicode):
                The app label for the app to purge.
        """
        super(PurgeAppTask, self).__init__(task_id='purge-app:%s' % app_label,
                                           evolver=evolver)

        self.app_label = app_label

    def prepare(self, **kwargs):
        """Prepare state for this task.

        This will determine if the app's tables need to be deleted from
        the database, and prepare the SQL for doing so.

        Args:
            **kwargs (dict, unused):
                Keyword arguments passed for task preparation.
        """
        evolver = self.evolver
        mutation = DeleteApplication()

        if self.is_mutation_mutable(mutation, app_label=self.app_label):
            app_mutator = AppMutator.from_evolver(
                evolver=evolver,
                app_label=self.app_label)
            app_mutator.run_mutation(mutation)

            self.evolution_required = True
            self.sql = app_mutator.to_sql()

        self.can_simulate = True
        self.new_evolutions = []

    def execute(self, cursor=None, sql_executor=None, **kwargs):
        """Execute the task.

        This will delete any tables owned by the application.

        Args:
            cursor (django.db.backends.util.CursorWrapper, unused):
                The legacy database cursor. This is no longer used.

            sql_executor (django_evolution.utils.sql.SQLExecutor, optional):
                The SQL executor used to run any SQL on the database.

        Raises:
            django_evolution.errors.EvolutionExecutionError:
                The evolution task failed. Details are in the error.
        """
        assert sql_executor

        if self.evolution_required:
            try:
                sql_executor.run_sql(self.sql, execute=True)
            except Exception as e:
                raise EvolutionExecutionError(
                    _('Error purging app "%s": %s')
                    % (self.app_label, e),
                    app_label=self.app_label,
                    detailed_error=six.text_type(e),
                    last_sql_statement=getattr(e, 'last_sql_statement'))

    def __str__(self):
        """Return a string description of the task.

        Returns:
            unicode:
            The string description.
        """
        return 'Purge application "%s"' % self.app_label

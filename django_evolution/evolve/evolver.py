"""Main Evolver interface for performing evolutions and migrations.

Version Added:
    2.2:
    This was previously located in :py:mod:`django_evolution.evolve`.
"""

from __future__ import unicode_literals

from collections import OrderedDict
from contextlib import contextmanager

from django.db import connections
from django.db.utils import DEFAULT_DB_ALIAS

from django_evolution.compat import six
from django_evolution.compat.apps import get_app, get_apps
from django_evolution.compat.db import atomic
from django_evolution.compat.translation import gettext as _
from django_evolution.db.state import DatabaseState
from django_evolution.diff import Diff
from django_evolution.errors import (EvolutionException,
                                     EvolutionTaskAlreadyQueuedError,
                                     EvolutionExecutionError,
                                     QueueEvolverTaskError)
from django_evolution.evolve.evolve_app_task import EvolveAppTask
from django_evolution.evolve.purge_app_task import PurgeAppTask
from django_evolution.models import Evolution, Version
from django_evolution.signals import evolved, evolving, evolving_failed
from django_evolution.signature import AppSignature, ProjectSignature
from django_evolution.utils.apps import get_app_label
from django_evolution.utils.sql import SQLExecutor


class Evolver(object):
    """The main class for managing database evolutions.

    The evolver is used to queue up tasks that modify the database. These
    allow for evolving database models and purging applications across an
    entire Django project or only for specific applications. Custom tasks
    can even be written by an application if very specific database
    operations need to be made outside of what's available in an evolution.

    Tasks are executed in order, but batched by the task type. That is, if
    two instances of ``TaskType1`` are queued, followed by an instance of
    ``TaskType2``, and another of ``TaskType1``, all 3 tasks of ``TaskType1``
    will be executed at once, with the ``TaskType2`` task following.

    Callers are expected to create an instance and queue up one or more tasks.
    Once all tasks are queued, the changes can be made using :py:meth:`evolve`.
    Alternatively, evolution hints can be generated using
    :py:meth:`generate_hints`.

    Projects will generally utilize this through the existing ``evolve``
    Django management command.

    Attributes:
        connection (django.db.backends.base.base.BaseDatabaseWrapper):
            The database connection object being used for the evolver.

        database_name (unicode):
            The name of the database being evolved.

        database_state (django_evolution.db.state.DatabaseState):
            The state of the database, for evolution purposes.

        evolved (bool):
            Whether the evolver has already performed its evolutions. These
            can only be done once per evolver.

        hinted (bool):
            Whether the evolver is operating against hinted evolutions. This
            may result in changes to the database without there being any
            accompanying evolution files backing those changes.

        interactive (bool):
            Whether the evolution operations are being performed in a
            way that allows interactivity on the command line. This is
            passed along to signal emissions.

        initial_diff (django_evolution.diff.Diff):
            The initial diff between the stored project signature and the
            current project signature.

        project_sig (django_evolution.signature.ProjectSignature):
            The project signature. This will start off as the previous
            signature stored in the database, but will be modified when
            mutations are simulated.

        verbosity (int):
            The verbosity level for any output. This is passed along to
            signal emissions.

        version (django_evolution.models.Version):
            The project version entry saved as the result of any evolution
            operations. This contains the current version of the project
            signature. It may be ``None`` until :py:meth:`evolve` is called.
    """

    def __init__(self, hinted=False, verbosity=0, interactive=False,
                 database_name=DEFAULT_DB_ALIAS):
        """Initialize the evolver.

        Args:
            hinted (bool, optional):
                Whether to operate against hinted evolutions. This may
                result in changes to the database without there being any
                accompanying evolution files backing those changes.

            verbosity (int, optional):
                The verbosity level for any output. This is passed along to
                signal emissions.

            interactive (bool, optional):
                Whether the evolution operations are being performed in a
                way that allows interactivity on the command line. This is
                passed along to signal emissions.

            database_name (unicode, optional):
                The name of the database to evolve.

        Raises:
            django_evolution.errors.EvolutionBaselineMissingError:
                An initial baseline for the project was not yet installed.
                This is due to ``syncdb``/``migrate`` not having been run.
        """
        self.database_name = database_name
        self.hinted = hinted
        self.verbosity = verbosity
        self.interactive = interactive

        self.evolved = False
        self.initial_diff = None
        self.project_sig = None
        self.version = None
        self.installed_new_database = False

        self.connection = connections[database_name]

        if hasattr(self.connection, 'prepare_database'):
            # Django >= 1.8
            self.connection.prepare_database()

        self.database_state = DatabaseState(self.database_name)
        self.target_project_sig = \
            ProjectSignature.from_database(database_name)

        self._tasks_by_class = OrderedDict()
        self._tasks_by_id = OrderedDict()
        self._tasks_prepared = False

        latest_version = None

        if self.database_state.has_model(Version):
            try:
                latest_version = \
                    Version.objects.current_version(using=database_name)
            except Version.DoesNotExist:
                # We'll populate this next.
                pass

        if latest_version is None:
            # Either the models aren't yet synced to the database, or we
            # don't have a saved project signature, so let's set these up.
            self.installed_new_database = True

            self.project_sig = ProjectSignature()
            app = get_app('django_evolution')

            task = EvolveAppTask(evolver=self,
                                 app=app)
            task.prepare(hinted=False)

            with self.sql_executor() as sql_executor:
                task.execute(sql_executor=sql_executor,
                             create_models_now=True)

            self.database_state.rescan_tables()

            app_sig = AppSignature.from_app(app=app,
                                            database=database_name)
            self.project_sig.add_app_sig(app_sig)

            # Let's make completely sure that we've only found the models
            # we expect. This is mostly for the benefit of unit tests.
            model_names = set(
                model_sig.model_name
                for model_sig in app_sig.model_sigs
            )
            expected_model_names = set(['Evolution', 'Version'])

            assert model_names == expected_model_names, (
                'Unexpected models found for django_evolution app: %s'
                % ', '.join(model_names - expected_model_names))

            self._save_project_sig(new_evolutions=task.new_evolutions)
            latest_version = self.version

        self.project_sig = latest_version.signature
        self.initial_diff = Diff(self.project_sig,
                                 self.target_project_sig)

    @property
    def tasks(self):
        """A list of all tasks that will be performed.

        This can only be accessed after all necessary tasks have been queued.
        """
        # If a caller is interested in the list of tasks, then it's likely
        # interested in state on those tasks. That means we'll need to prepare
        # all the tasks before we can return any of them.
        self._prepare_tasks()

        return six.itervalues(self._tasks_by_id)

    def can_simulate(self):
        """Return whether all queued tasks can be simulated.

        If any tasks cannot be simulated (for instance, a hinted evolution
        requiring manually-entered values), then this will return ``False``.

        This can only be called after all tasks have been queued.

        Returns:
            bool:
            ``True`` if all queued tasks can be simulated. ``False`` if any
            cannot.
        """
        return all(
            task.can_simulate or not task.evolution_required
            for task in self.tasks
        )

    def get_evolution_required(self):
        """Return whether there are any evolutions required.

        This can only be called after all tasks have been queued.

        Returns:
            bool:
            ``True`` if any tasks require evolution. ``False`` if none do.
        """
        return any(
            task.evolution_required
            for task in self.tasks
        )

    def diff_evolutions(self):
        """Return a diff between stored and post-evolution project signatures.

        This will run through all queued tasks, preparing them and simulating
        their changes. The returned diff will represent the changes made in
        those tasks.

        This can only be called after all tasks have been queued.

        Returns:
            django_evolution.diff.Diff:
            The diff between the stored signature and the queued changes.
        """
        self._prepare_tasks()

        return Diff(self.project_sig, self.target_project_sig)

    def iter_evolution_content(self):
        """Generate the evolution content for all queued tasks.

        This will loop through each tasks and yield any evolution content
        provided.

        This can only be called after all tasks have been queued.

        Yields:
            tuple:
            A tuple of ``(task, evolution_content)``.
        """
        for task in self.tasks:
            content = task.get_evolution_content()

            if content:
                yield task, content

    def queue_evolve_all_apps(self):
        """Queue an evolution of all registered Django apps.

        This cannot be used if :py:meth:`queue_evolve_app` is also being used.

        Raises:
            django_evolution.errors.EvolutionTaskAlreadyQueuedError:
                An evolution for an app was already queued.

            django_evolution.errors.QueueEvolverTaskError:
                Error queueing a non-duplicate task. Tasks may have already
                been prepared and finalized.
        """
        for app in get_apps():
            self.queue_evolve_app(app)

    def queue_evolve_app(self, app):
        """Queue an evolution of a registered Django app.

        Args:
            app (module):
                The Django app to queue an evolution for.

        Raises:
            django_evolution.errors.EvolutionTaskAlreadyQueuedError:
                An evolution for this app was already queued.

            django_evolution.errors.QueueEvolverTaskError:
                Error queueing a non-duplicate task. Tasks may have already
                been prepared and finalized.
        """
        try:
            self.queue_task(EvolveAppTask(self, app))
        except EvolutionTaskAlreadyQueuedError:
            raise EvolutionTaskAlreadyQueuedError(
                _('"%s" is already being tracked for evolution')
                % get_app_label(app))

    def queue_purge_old_apps(self):
        """Queue the purging of all old, stale Django apps.

        This will purge any apps that exist in the stored project signature
        but that are no longer registered in Django.

        This generally should not be used if :py:meth:`queue_purge_app` is also
        being used.

        Raises:
            django_evolution.errors.EvolutionTaskAlreadyQueuedError:
                A purge of an app was already queued.

            django_evolution.errors.QueueEvolverTaskError:
                Error queueing a non-duplicate task. Tasks may have already
                been prepared and finalized.
        """
        for app_label in self.initial_diff.deleted:
            self.queue_purge_app(app_label)

    def queue_purge_app(self, app_label):
        """Queue the purging of a Django app.

        Args:
            app_label (unicode):
                The label of the app to purge.

        Raises:
            django_evolution.errors.EvolutionTaskAlreadyQueuedError:
                A purge of this app was already queued.

            django_evolution.errors.QueueEvolverTaskError:
                Error queueing a non-duplicate task. Tasks may have already
                been prepared and finalized.
        """
        try:
            self.queue_task(PurgeAppTask(evolver=self,
                                         app_label=app_label))
        except EvolutionTaskAlreadyQueuedError:
            raise EvolutionTaskAlreadyQueuedError(
                _('"%s" is already being tracked for purging')
                % app_label)

    def queue_task(self, task):
        """Queue a task to run during evolution.

        This should only be directly called if working with custom tasks.
        Otherwise, use a more specific queue method.

        Args:
            task (BaseEvolutionTask):
                The task to queue.

        Raises:
            django_evolution.errors.EvolutionTaskAlreadyQueuedError:
                A purge of this app was already queued.

            django_evolution.errors.QueueEvolverTaskError:
                Error queueing a non-duplicate task. Tasks may have already
                been prepared and finalized.

        """
        assert task.id

        if self._tasks_prepared:
            raise QueueEvolverTaskError(
                _('Evolution tasks have already been prepared. New tasks '
                  'cannot be added.'))

        if task.id in self._tasks_by_id:
            raise EvolutionTaskAlreadyQueuedError(
                _('A task with ID "%s" is already queued.')
                % task.id)

        self._tasks_by_id[task.id] = task
        self._tasks_by_class.setdefault(type(task), []).append(task)

    def evolve(self):
        """Perform the evolution.

        This will run through all queued tasks and attempt to apply them in
        a database transaction, tracking each new batch of evolutions as the
        tasks finish.

        This can only be called once per evolver instance.

        Raises:
            django_evolution.errors.EvolutionException:
                Something went wrong during the evolution process. Details
                are in the error message. Note that a more specific exception
                may be raised.

            django_evolution.errors.EvolutionExecutionError:
                A specific evolution task failed. Details are in the error.
        """
        if self.evolved:
            raise EvolutionException(
                _('Evolver.evolve() has already been run once. It cannot be '
                  'run again.'))

        self._prepare_tasks()

        evolving.send(sender=self)

        try:
            new_evolutions = []

            for task_cls, tasks in six.iteritems(self._tasks_by_class):
                # Perform the evolution for the app. This is responsible
                # for raising any exceptions.
                task_cls.execute_tasks(evolver=self,
                                       tasks=tasks)

                for task in tasks:
                    new_evolutions += task.new_evolutions

                # Things may have changed, so rescan the database.
                self.database_state.rescan_tables()

            self._save_project_sig(new_evolutions=new_evolutions)
            self.evolved = True
        except Exception as e:
            evolving_failed.send(sender=self,
                                 exception=e)
            raise

        evolved.send(sender=self)

    def _prepare_tasks(self):
        """Prepare all queued tasks for further operations.

        Once prepared, no new tasks can be added. This will be done before
        performing any operations requiring state from queued tasks.
        """
        if not self._tasks_prepared:
            self._tasks_prepared = True

            for task_cls, tasks in six.iteritems(self._tasks_by_class):
                task_cls.prepare_tasks(evolver=self,
                                       tasks=tasks,
                                       hinted=self.hinted)

    def sql_executor(self, **kwargs):
        """Return an SQLExecutor for executing SQL.

        This is a convenience method for creating an
        :py:class:`~django_evolution.utils.sql.SQLExecutor` to operate using
        the evolver's current database.

        Version Added:
            2.1

        Args:
            **kwargs (dict):
                Additional keyword arguments used to construct the executor.

        Returns:
            django_evolution.utils.sql.SQLExecutor:
            The new SQLExecutor.
        """
        return SQLExecutor(database=self.database_name, **kwargs)

    @contextmanager
    def transaction(self):
        """Execute database operations in a transaction.

        This is a convenience method for executing in a transaction using
        the evolver's current database.

        Deprecated:
            2.1:
            This has been replaced with manual calls to
            :py:class:`~django_evolution.utils.sql.SQLExecutor`.

        Context:
            django.db.backends.util.CursorWrapper:
            The cursor used to execute statements.
        """
        with atomic(using=self.database_name):
            cursor = self.connection.cursor()

            try:
                yield cursor
            finally:
                cursor.close()

    def _save_project_sig(self, new_evolutions):
        """Save the project signature and any new evolutions.

        This will serialize the current modified project signature to the
        database and write any new evolutions, attaching them to the current
        project version.

        This can be called many times for one evolver instance. After the
        first time, the version already saved will simply be updated.

        Args:
            new_evolutions (list of django_evolution.models.Evolution):
                The list of new evolutions to save to the database.

        Raises:
            django_evolution.errors.EvolutionExecutionError:
                There was an error saving to the database.
        """
        version = self.version

        if version is None:
            version = Version(signature=self.project_sig)
            self.version = version

        try:
            version.save(using=self.database_name)

            if new_evolutions:
                for evolution in new_evolutions:
                    evolution.version = version

                Evolution.objects.using(self.database_name).bulk_create(
                    new_evolutions)
        except Exception as e:
            raise EvolutionExecutionError(
                _('Error saving new evolution version information: %s')
                % e,
                detailed_error=six.text_type(e))

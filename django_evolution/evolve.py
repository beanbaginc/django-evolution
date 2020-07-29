"""Main interface for evolving applications."""

from __future__ import unicode_literals

import itertools
import logging
from collections import OrderedDict
from contextlib import contextmanager

from django.db import DatabaseError, connections
from django.db.utils import DEFAULT_DB_ALIAS
from django.utils.translation import ugettext as _

from django_evolution.compat import six
from django_evolution.compat.apps import get_app, get_apps
from django_evolution.compat.db import (atomic,
                                        db_get_installable_models_for_app,
                                        sql_create_models)
from django_evolution.consts import UpgradeMethod
from django_evolution.db.state import DatabaseState
from django_evolution.diff import Diff
from django_evolution.errors import (EvolutionException,
                                     EvolutionTaskAlreadyQueuedError,
                                     EvolutionExecutionError,
                                     QueueEvolverTaskError)
from django_evolution.models import Evolution, Version
from django_evolution.mutations import AddField, DeleteApplication
from django_evolution.mutators import AppMutator
from django_evolution.signals import (applied_evolution,
                                      applying_evolution,
                                      created_models,
                                      creating_models,
                                      evolved,
                                      evolving,
                                      evolving_failed)
from django_evolution.signature import AppSignature, ProjectSignature
from django_evolution.support import supports_migrations
from django_evolution.utils.apps import get_app_label, get_legacy_app_label
from django_evolution.utils.evolutions import (get_app_pending_mutations,
                                               get_evolution_sequence,
                                               get_unapplied_evolutions)
from django_evolution.utils.migrations import (MigrationExecutor,
                                               MigrationList,
                                               apply_migrations,
                                               create_pre_migrate_state,
                                               emit_post_migrate_or_sync,
                                               emit_pre_migrate_or_sync,
                                               filter_migration_targets,
                                               finalize_migrations,
                                               is_migration_initial,
                                               record_applied_migrations)
from django_evolution.utils.sql import execute_sql


logger = logging.getLogger(__name__)


class BaseEvolutionTask(object):
    """Base class for a task to perform during evolution.

    Attributes:
        can_simulate (bool):
            Whether the task can be simulated without requiring additional
            information.

            This is set after calling :py:meth:`prepare`.

        evolution_required (bool):
            Whether an evolution is required by this task.

            This is set after calling :py:meth:`prepare`.

        evolver (Evolver):
            The evolver that will execute the task.

        id (unicode):
            The unique ID for the task.

        new_evolutions (list of django_evolution.models.Evolution):
            A list of evolution model entries this task would create.

            This is set after calling :py:meth:`prepare`.

        sql (list):
            A list of SQL statements to perform for the task. Each entry can
            be a string or tuple accepted by
            :py:func:`~django_evolution.utils.execute_sql`.
    """

    @classmethod
    def prepare_tasks(cls, evolver, tasks, **kwargs):
        """Prepare a list of tasks.

        This is responsible for calling :py:meth:`prepare` on each of the
        provided tasks. It can augment this by calculating any other state
        needed in order to influence the tasks or react to them.

        If this applies state to the class, it should always be careful to
        completely reset the state on each run, in case there are multiple
        :py:class:`Evolver` instances at work within a process.

        Args:
            evolver (Evolver):
                The evolver that's handling the tasks.

            tasks (list of BaseEvolutionTask):
                The list of tasks to prepare. These will match the current
                class.

            **kwargs (dict):
                Keyword arguments to pass to the tasks' `:py:meth:`prepare`
                methods.
        """
        for task in tasks:
            task.prepare(**kwargs)

    @classmethod
    def execute_tasks(cls, evolver, tasks, **kwargs):
        """Execute a list of tasks.

        This is responsible for calling :py:meth:`execute` on each of the
        provided tasks. It can augment this by executing any steps before or
        after the tasks.

        If this applies state to the class, it should always be careful to
        completely reset the state on each run, in case there are multiple
        :py:class:`Evolver` instances at work within a process.

        This may depend on state from :py:meth:`prepare_tasks`.

        Args:
            evolver (Evolver):
                The evolver that's handling the tasks.

            tasks (list of BaseEvolutionTask):
                The list of tasks to execute. These will match the current
                class.

            **kwargs (dict):
                Keyword arguments to pass to the tasks' `:py:meth:`execute`
                methods.
        """
        with evolver.connection.constraint_checks_disabled():
            with evolver.transaction() as cursor:
                for task in tasks:
                    task.execute(cursor=cursor, **kwargs)

    def __init__(self, task_id, evolver):
        """Initialize the task.

        Args:
            task_id (unicode):
                The unique ID for the task.

            evolver (Evolver):
                The evolver that will execute the task.
        """
        self.id = task_id
        self.evolver = evolver

        self.can_simulate = False
        self.evolution_required = False
        self.new_evolutions = []
        self.sql = []

    def is_mutation_mutable(self, mutation, **kwargs):
        """Return whether a mutation is mutable.

        This is a handy wrapper around :py:meth:`BaseMutation.is_mutable
        <django_evolution.mutations.BaseMutation.is_mutable>` that passes
        standard arguments based on evolver state. Callers should pass any
        additional arguments that are required as keyword arguments.

        Args:
            mutation (django_evolution.mutations.BaseMutation):
                The mutation to check.

            **kwargs (dict):
                Additional keyword arguments to pass to
                :py:meth:`BaseMutation.is_mutable
                <django_evolution.mutations.BaseMutation.is_mutable>`.

        Returns:
            bool:
            ``True`` if the mutation is mutable. ``False`` if it is not.
        """
        evolver = self.evolver

        return mutation.is_mutable(project_sig=evolver.project_sig,
                                   database_state=evolver.database_state,
                                   database=evolver.database_name,
                                   **kwargs)

    def prepare(self, hinted, **kwargs):
        """Prepare state for this task.

        This is responsible for determining whether the task applies to the
        database. It must set :py:attr:`evolution_required`,
        :py:attr:`new_evolutions`, and :py:attr:`sql`.

        This must be called before :py:meth:`execute` or
        :py:meth:`get_evolution_content`.

        Args:
            hinted (bool):
                Whether to prepare the task for hinted evolutions.

            **kwargs (dict, unused):
                Additional keyword arguments passed for task preparation.
                This is provide for future expansion purposes.
        """
        raise NotImplementedError

    def execute(self, cursor):
        """Execute the task.

        This will make any changes necessary to the database.

        Args:
            cursor (django.db.backends.util.CursorWrapper):
                The database cursor used to execute queries.

        Raises:
            django_evolution.errors.EvolutionExecutionError:
                The evolution task failed. Details are in the error.
        """
        raise NotImplementedError

    def get_evolution_content(self):
        """Return the content for an evolution file for this task.

        Returns:
            unicode:
            The evolution content.
        """
        raise NotImplementedError

    def __str__(self):
        """Return a string description of the task.

        Returns:
            unicode:
            The string description.
        """
        raise NotImplementedError


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

    def execute(self, cursor):
        """Execute the task.

        This will delete any tables owned by the application.

        Args:
            cursor (django.db.backends.util.CursorWrapper):
                The database cursor used to execute queries.

        Raises:
            django_evolution.errors.EvolutionExecutionError:
                The evolution task failed. Details are in the error.
        """
        if self.evolution_required:
            try:
                execute_sql(cursor, self.sql, self.evolver.database_name)
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


class EvolveAppTask(BaseEvolutionTask):
    """A task for evolving models in an application.

    This task will run through any evolutions in the provided application and
    handle applying each of those evolutions that haven't yet been applied.

    Attributes:
        app (module):
            The app module to evolve.

        app_label (unicode):
            The app label for the app to evolve.
    """

    @classmethod
    def prepare_tasks(cls, evolver, tasks, **kwargs):
        """Prepare a list of tasks.

        If migrations are supported, then before preparing any of the tasks,
        this will begin setting up state needed to apply any migrations for
        apps that use them (or will use them after any evolutions are applied).

        After tasks are prepared, this will apply any migrations that need to
        be applied, updating the app's signature appropriately and recording
        all applied migrations.

        Args:
            evolver (Evolver):
                The evolver that's handling the tasks.

            tasks (list of BaseEvolutionTask):
                The list of tasks to prepare. These will match the current
                class.

            **kwargs (dict):
                Keyword arguments to pass to the tasks' `:py:meth:`prepare`
                methods.

        Raises:
            django_evolution.errors.BaseMigrationError:
                There was an error with the setup or validation of migrations.
                A subclass containing additional details will be raised.
        """
        connection = evolver.connection

        # We're going to be performing up to two migration phases. The first
        # phase ("pre") handles any initial migrations that create tables,
        # so that any evolution-backed apps can establish relations to them.
        # The second phase ("post") handles any subsequent migrations.
        pre_migration_plan = None
        pre_migration_targets = None

        post_migration_plan = None
        post_migration_targets = None

        full_migration_plan = None
        pre_migrate_state = None

        migration_executor = None

        if supports_migrations:
            custom_migrations = MigrationList()

            for task in tasks:
                for migration in task._migrations or []:
                    custom_migrations.add_migration(migration)

            migration_executor = MigrationExecutor(
                connection=connection,
                signal_sender=evolver,
                custom_migrations=custom_migrations)
            migration_executor.run_checks()

        # Run through the tasks, collecting all the SQL for installing new
        # models and for applying evolutions to existing ones.
        super(EvolveAppTask, cls).prepare_tasks(
            evolver=evolver,
            tasks=tasks,
            **kwargs)

        if supports_migrations:
            # Now that we have updated signatures from any evolutions (which
            # may have applied MoveToDjangoMigrations mutators), we can start
            # to figure out the migration plan.
            migration_loader = migration_executor.loader
            extra_applied_migrations = \
                migration_loader.extra_applied_migrations
            assert not extra_applied_migrations

            applied_migrations = MigrationList.from_database(connection)
            migration_app_labels = set()

            # Run through the new applied migrations marked in any app
            # signatures and find any that we're planning to record.
            for task in tasks:
                if (task.app_sig is not None and
                    task.app_sig.upgrade_method == UpgradeMethod.MIGRATIONS):
                    app_label = task.app_label
                    migration_app_labels.add(app_label)

                    # Figure out which applied migrations the mutator or
                    # signature listed that we don't have in the database.
                    new_applied_migrations = (
                        MigrationList.from_app_sig(task.app_sig) -
                        applied_migrations)

                    if new_applied_migrations:
                        # We found some. Mark them as being applied. We'll
                        # record them during the execution phase.
                        extra_applied_migrations.update(new_applied_migrations)

            if migration_app_labels:
                if extra_applied_migrations:
                    # Rebuild the migration graph, based on anything we've
                    # added above, and re-run checks.
                    migration_loader.build_graph()
                    migration_executor.run_checks()

                # Build the lists of migration targets we'll be applying. Each
                # entry lists an app label and a migration name. We're
                # limiting these to the apps we know we'll be migrating.
                excluded_targets = (applied_migrations +
                                    extra_applied_migrations).to_targets()

                # First, generate a full migration plan that covers the entire
                # beginning to end of the process. We'll use this for signal
                # emissions.
                full_migration_targets = filter_migration_targets(
                    targets=migration_loader.graph.leaf_nodes(),
                    app_labels=migration_app_labels)

                if full_migration_targets:
                    full_migration_plan = migration_executor.migration_plan(
                        full_migration_targets)

                pre_migrate_state = \
                    create_pre_migrate_state(migration_executor)

                # First, try to find all the initial migrations. These will
                # be ones that are root migrations (have no parents in the
                # app) and aren't already marked as applied.
                pre_migration_targets = []
                root_migration_targets = filter_migration_targets(
                    targets=migration_loader.graph.root_nodes(),
                    app_labels=migration_app_labels,
                    exclude=excluded_targets)

                for migration_target in root_migration_targets:
                    migration = \
                        migration_loader.get_migration(*migration_target)

                    if is_migration_initial(migration):
                        pre_migration_targets.append(migration_target)

                if pre_migration_targets:
                    pre_migration_plan = migration_executor.migration_plan(
                        pre_migration_targets)

                    excluded_targets.update(pre_migration_targets)
                    extra_applied_migrations.add_migration_targets(
                        pre_migration_targets)
                    migration_loader.build_graph(reload_migrations=False)
                    migration_executor.run_checks()

                # Now try to find all the migrations we'd want to apply after
                # any evolutions take place. These will be ones that haven't
                # already been applied and haven't been handled in the pre
                # migration set.
                post_migration_targets = filter_migration_targets(
                    targets=migration_loader.graph.leaf_nodes(),
                    app_labels=migration_app_labels,
                    exclude=excluded_targets)

                if post_migration_targets:
                    post_migration_plan = migration_executor.migration_plan(
                        post_migration_targets)
            else:
                # We may not be migrating, but we still want this state
                # for signal emissions, so create it now.
                pre_migrate_state = \
                    create_pre_migrate_state(migration_executor)

            # If we don't have anything to do, unset the state. Everything
            # but pre_migrate_state, since we'll still want it for signal
            # emissions.
            if not pre_migration_plan:
                pre_migration_plan = None
                pre_migration_targets = None

            if not post_migration_plan:
                post_migration_plan = None
                post_migration_targets = None

            if not pre_migration_plan and not post_migration_plan:
                migration_executor = None
                full_migration_plan = None

        cls._migration_executor = migration_executor
        cls._pre_migration_plan = pre_migration_plan
        cls._pre_migration_targets = pre_migration_targets
        cls._post_migration_plan = post_migration_plan
        cls._post_migration_targets = post_migration_targets
        cls._pre_migrate_state = pre_migrate_state
        cls._full_migration_plan = full_migration_plan

    @classmethod
    def execute_tasks(cls, evolver, tasks, **kwargs):
        """Execute a list of tasks.

        This is responsible for calling :py:meth:`execute` on each of the
        provided tasks. It can augment this by executing any steps before or
        after the tasks.

        Args:
            evolver (Evolver):
                The evolver that's handling the tasks.

            tasks (list of BaseEvolutionTask):
                The list of tasks to execute. These will match the current
                class.

            cursor (django.db.backends.util.CursorWrapper):
                The database cursor used to execute queries.

            **kwargs (dict):
                Keyword arguments to pass to the tasks' `:py:meth:`execute`
                methods.
        """
        migrate_state = cls._pre_migrate_state
        migrating = cls._full_migration_plan is not None
        new_models = list(itertools.chain.from_iterable(
            task.new_models
            for task in tasks
        ))

        if migrating:
            # If we have any applied migration names we wanted to record, do it
            # before we begin any migrations.
            applied_migrations = \
                cls._migration_executor.loader.extra_applied_migrations

            if applied_migrations:
                record_applied_migrations(connection=evolver.connection,
                                          migrations=applied_migrations)

        # Let any listeners know that we're beginning the process.
        emit_pre_migrate_or_sync(verbosity=evolver.verbosity,
                                 interactive=evolver.interactive,
                                 database_name=evolver.database_name,
                                 create_models=new_models,
                                 pre_migrate_state=migrate_state,
                                 plan=cls._full_migration_plan)

        if migrating:
            if migrate_state:
                migrate_state = migrate_state.clone()

            # First, apply all initial migrations for the apps, generating any
            # tables that are needed. This ensures that evolution-backed apps
            # can make references to those.
            if cls._pre_migration_plan:
                migrate_state = apply_migrations(
                    executor=cls._migration_executor,
                    targets=cls._pre_migration_targets,
                    plan=cls._pre_migration_plan,
                    pre_migrate_state=migrate_state)

        # Next, create all new database models for all non-migration-backed
        # apps. We can then work on evolving/migrating those apps.
        with evolver.connection.constraint_checks_disabled():
            with evolver.transaction() as cursor:
                for task in tasks:
                    if task.new_models_sql:
                        task._create_models(cursor)

                # Process any evolutions for the apps.
                for task in tasks:
                    task.execute(cursor=cursor, **kwargs)

        if migrating:
            if cls._post_migration_plan:
                # Now finish up by applying any subsequent migrations.
                migrate_state = apply_migrations(
                    executor=cls._migration_executor,
                    targets=cls._post_migration_targets,
                    plan=cls._post_migration_plan,
                    pre_migrate_state=migrate_state)

            cls._post_migrate_state = migrate_state
            finalize_migrations(migrate_state)

            # Write the new lists of applied migrations out to the signature.
            applied_migrations = \
                MigrationList.from_database(evolver.connection)
            project_sig = evolver.project_sig

            for app_label in applied_migrations.get_app_labels():
                app_sig = project_sig.get_app_sig(app_label, required=True)

                # The signature will take care of storing only the migrations
                # that apply to it when we assign this.
                app_sig.applied_migrations = applied_migrations

        # Let any listeners know that we've finished the process.
        emit_post_migrate_or_sync(verbosity=evolver.verbosity,
                                  interactive=evolver.interactive,
                                  database_name=evolver.database_name,
                                  created_models=new_models,
                                  post_migrate_state=migrate_state,
                                  plan=cls._full_migration_plan)

    def __init__(self, evolver, app, evolutions=None, migrations=None):
        """Initialize the task.

        Args:
            evolver (Evolver):
                The evolver that will execute the task.

            app (module):
                The app module to evolve.

            evolutions (list of dict, optional):
                Optional evolutions to use for the app instead of loading
                from a file. This is intended for testing purposes.

                Each dictionary needs a ``label`` key for the evolution label
                and a ``mutations`` key for a list of
                :py:class:`~django_evolution.mutations.BaseMutation` instances.

            migrations (list of django.db.migrations.Migration, optional):
                Optional migrations to use for the app instead of loading from
                files. This is intended for testing purposes.
        """
        super(EvolveAppTask, self).__init__(
            task_id='evolve-app:%s' % app.__name__,
            evolver=evolver)

        self.app = app
        self.app_label = get_app_label(app)
        self.legacy_app_label = get_legacy_app_label(app)

        self.app_sig = None
        self.new_models_sql = []
        self.new_model_names = []
        self.new_models = []

        self._evolutions = evolutions
        self._migrations = migrations
        self._mutations = None

    def prepare(self, hinted=False, **kwargs):
        """Prepare state for this task.

        This will determine if there are any unapplied evolutions in the app,
        and record that state and the SQL needed to apply the evolutions.

        Args:
            hinted (bool, optional):
                Whether to prepare the task for hinted evolutions.

            **kwargs (dict, unused):
                Additional keyword arguments passed for task preparation.
        """
        app = self.app
        app_label = self.app_label
        evolver = self.evolver
        database_name = evolver.database_name
        project_sig = evolver.project_sig

        # Check if there are any models for this app that don't yet exist
        # in the database.
        new_models = db_get_installable_models_for_app(
            app=app,
            db_state=evolver.database_state)

        self.new_models = new_models
        self.new_model_names = [
            model._meta.object_name
            for model in new_models
        ]

        # See if we're already tracking this app in the signature.
        app_sig = (project_sig.get_app_sig(app_label) or
                   project_sig.get_app_sig(self.legacy_app_label))
        app_sig_is_new = app_sig is None
        orig_upgrade_method = None

        target_project_sig = evolver.target_project_sig
        target_app_sig = target_project_sig.get_app_sig(app_label,
                                                        required=True)
        evolutions = []

        if new_models:
            # Record what we know so far about the state. We might find that
            # we can't simulate once we process evolutions.
            self.can_simulate = True
            self.evolution_required = True

        if app_sig_is_new:
            # We're adding this app for the first time. If there are models
            # here, then copy the entire signature from the target, and mark
            # all evolutions for the app as applied.
            if new_models:
                app_sig = target_app_sig.clone()
                project_sig.add_app_sig(app_sig)

                evolutions = get_evolution_sequence(app)
                orig_upgrade_method = app_sig.upgrade_method
        else:
            orig_upgrade_method = app_sig.upgrade_method

            # Copy only the models from the target signature that have
            # been created.
            for model in new_models:
                target_model_sig = target_app_sig.get_model_sig(
                    model._meta.object_name,
                    required=True)

                app_sig.add_model_sig(target_model_sig.clone())

            if app_sig.upgrade_method != UpgradeMethod.MIGRATIONS:
                # We're processing this as evolutions. Find out if we're
                # applying/generating selective evolutions, hinted evolutions,
                # or existing unapplied evolutions.
                if self._evolutions is not None:
                    evolutions = []
                    pending_mutations = []

                    for evolution in self._evolutions:
                        evolutions.append(evolution['label'])
                        pending_mutations += evolution['mutations']
                elif hinted:
                    evolutions = []
                    hinted_evolution = evolver.initial_diff.evolution()
                    pending_mutations = hinted_evolution.get(self.app_label,
                                                             [])
                else:
                    evolutions = get_unapplied_evolutions(
                        app=app,
                        database=database_name)
                    pending_mutations = get_app_pending_mutations(
                        app=app,
                        evolution_labels=evolutions,
                        database=database_name)

                mutations = [
                    mutation
                    for mutation in pending_mutations
                    if self.is_mutation_mutable(mutation,
                                                app_label=self.app_label)
                ]

                if mutations:
                    app_mutator = AppMutator.from_evolver(
                        evolver=evolver,
                        app_label=self.app_label,
                        legacy_app_label=self.legacy_app_label)
                    app_mutator.run_mutations(mutations)

                    self.can_simulate = app_mutator.can_simulate
                    self.sql = app_mutator.to_sql()
                    self.evolution_required = True
                    self._mutations = mutations

        if new_models:
            # We're creating the models for the first time. We want to do this
            # in the most appropriate way. If we're working with a brand-new
            # app, which ultimately uses migrations, then we want to use
            # those migrations in order to build the models (so subsequent
            # migrations will apply on top of it cleanly).
            use_migrations = (
                supports_migrations and
                orig_upgrade_method == UpgradeMethod.MIGRATIONS)

            if use_migrations:
                logger.debug('Using migrations to create models for %s',
                             app_label)
            else:
                logger.debug('Using SQL to create models for %s',
                             app_label)
                self.new_models_sql = sql_create_models(new_models,
                                                        db_name=database_name)

        self.app_sig = app_sig
        self.new_evolutions = [
            Evolution(app_label=app_label,
                      label=label)
            for label in evolutions
        ]

    def execute(self, cursor, create_models_now=False):
        """Execute the task.

        This will apply any evolutions queued up for the app.

        Before the evolutions are applied for the app, the
        :py:data:`~django_evolution.signals.applying_evolution` signal will
        be emitted. After,
        :py:data:`~django_evolution.signals.applied_evolution` will be emitted.

        Args:
            cursor (django.db.backends.util.CursorWrapper):
                The database cursor used to execute queries.

            create_models_now (bool, optional):
                Whether to create models as part of this execution. Normally,
                this is handled in :py:meth:`execute_tasks`, but this flag
                allows for more fine-grained control of table creation in
                limited circumstances (intended only by :py:class:`Evolver`).

        Raises:
            django_evolution.errors.EvolutionExecutionError:
                The evolution task failed. Details are in the error.
        """
        if create_models_now and self.new_models_sql:
            self._create_models(cursor)

        if self.sql:
            applying_evolution.send(sender=self.evolver,
                                    task=self)

            try:
                execute_sql(cursor, self.sql, self.evolver.database_name)
            except Exception as e:
                raise EvolutionExecutionError(
                    _('Error applying evolution for %s: %s')
                    % (self.app_label, e),
                    app_label=self.app_label,
                    detailed_error=six.text_type(e),
                    last_sql_statement=getattr(e, 'last_sql_statement'))

            applied_evolution.send(sender=self.evolver,
                                   task=self)

    def get_evolution_content(self):
        """Return the content for an evolution file for this task.

        Returns:
            unicode:
            The evolution content.
        """
        if not self._mutations:
            return None

        imports = set()
        project_imports = set()
        mutation_types = set()
        mutation_lines = []

        app_prefix = self.app.__name__.split('.')[0]

        for mutation in self._mutations:
            mutation_types.add(type(mutation).__name__)
            mutation_lines.append('    %s,' % mutation)

            if isinstance(mutation, AddField):
                field_module = mutation.field_type.__module__

                if field_module.startswith('django.db.models'):
                    imports.add('from django.db import models')
                else:
                    import_str = ('from %s import %s' %
                                  (field_module, mutation.field_type.__name__))

                    if field_module.startswith(app_prefix):
                        project_imports.add(import_str)
                    else:
                        imports.add(import_str)

        imports.add('from django_evolution.mutations import %s'
                    % ', '.join(sorted(mutation_types)))

        lines = [
            'from __future__ import unicode_literals',
            '',
        ] + sorted(imports)

        lines.append('')

        if project_imports:
            lines += sorted(project_imports)
            lines.append('')

        lines += [
            '',
            'MUTATIONS = [',
        ] + mutation_lines + [
            ']',
        ]

        return '\n'.join(lines)

    def __str__(self):
        """Return a string description of the task.

        Returns:
            unicode:
            The string description.
        """
        return 'Evolve application "%s"' % self.app_label

    def _create_models(self, cursor):
        """Create tables for models in the database.

        Args:
            cursor (django.db.backends.util.CursorWrapper):
                The database cursor used to install the models.
        """
        app_label = self.app_label
        evolver = self.evolver
        new_model_names = self.new_model_names

        creating_models.send(sender=evolver,
                             app_label=app_label,
                             model_names=new_model_names)

        try:
            execute_sql(cursor,
                        self.new_models_sql,
                        evolver.database_name)
        except Exception as e:
            raise EvolutionExecutionError(
                _('Error creating database models for %s: %s')
                % (app_label, e),
                app_label=app_label,
                detailed_error=six.text_type(e),
                last_sql_statement=getattr(e, 'last_sql_statement'))

        created_models.send(sender=evolver,
                            app_label=app_label,
                            model_names=new_model_names)


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

        try:
            latest_version = \
                Version.objects.current_version(using=database_name)
        except (DatabaseError, Version.DoesNotExist):
            # Either the models aren't yet synced to the database, or we
            # don't have a saved project signature, so let's set these up.
            self.project_sig = ProjectSignature()
            app = get_app('django_evolution')

            task = EvolveAppTask(evolver=self,
                                 app=app)
            task.prepare(hinted=False)

            with self.transaction() as cursor:
                task.execute(cursor, create_models_now=True)

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

    @contextmanager
    def transaction(self):
        """Execute database operations in a transaction.

        This is a convenience method for executing in a transaction using
        the evolver's current database.

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

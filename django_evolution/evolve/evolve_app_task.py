"""Task for evolving an application.

Version Added:
    2.2:
    This was previously located in :py:mod:`django_evolution.evolve`.
"""

from __future__ import unicode_literals

import itertools
import logging
from collections import OrderedDict

from django_evolution.compat import six
from django_evolution.compat.db import (db_get_installable_models_for_app,
                                        sql_create_models)
from django_evolution.compat.translation import gettext as _
from django_evolution.consts import UpgradeMethod
from django_evolution.errors import EvolutionExecutionError
from django_evolution.evolve.base import BaseEvolutionTask
from django_evolution.models import Evolution
from django_evolution.mutations import AddField
from django_evolution.mutators import AppMutator
from django_evolution.signals import (applied_evolution,
                                      applying_evolution,
                                      created_models,
                                      creating_models)
from django_evolution.support import supports_migrations
from django_evolution.utils.apps import get_app_label, get_legacy_app_label
from django_evolution.utils.datastructures import (filter_dup_list_items,
                                                   merge_dicts)
from django_evolution.utils.evolutions import (get_app_pending_mutations,
                                               get_app_upgrade_info,
                                               get_applied_evolutions,
                                               get_evolution_sequence,
                                               get_unapplied_evolutions)
from django_evolution.utils.graph import EvolutionGraph
from django_evolution.utils.migrations import (
    MigrationExecutor,
    MigrationList,
    apply_migrations,
    clear_global_custom_migrations,
    create_pre_migrate_state,
    emit_post_migrate_or_sync,
    emit_pre_migrate_or_sync,
    filter_migration_targets,
    finalize_migrations,
    is_migration_initial,
    record_applied_migrations,
    register_global_custom_migrations)


logger = logging.getLogger(__name__)


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
    def prepare_tasks(cls, evolver, tasks, hinted=False, **kwargs):
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
        # Register any custom migrations that we want globally available.
        # This is of course not thread-safe, but nobody should be doing
        # concurrent migrations, or they're in for a pretty bad time.
        if supports_migrations:
            custom_migrations = MigrationList()

            for task in tasks:
                for migration in task._migrations or []:
                    custom_migrations.add_migration(migration)

            register_global_custom_migrations(custom_migrations)

        # We're going to let Django determine a plan for all migrations, and
        # we'll determine a plan for evolutions. These will be combined into a
        # dependency graph, which will produce the order in which we'll need
        # to apply migrations and evolutions.
        #
        # First, run through the tasks, preparing state that we'll use to
        # build the migrations and evolutions graph and resulting batches.
        super(EvolveAppTask, cls).prepare_tasks(
            evolver=evolver,
            tasks=tasks,
            hinted=hinted,
            **kwargs)

        # Now we can generate the remaining state needed to determine the
        # order in which migrations and evolutions need to be applied. We'll
        # compute the migration plans, build a graph from it, and then
        # convert that into batches for execution.
        migration_executor = cls._build_migration_executor(
            evolver=evolver,
            tasks=tasks)
        migrations_info = cls._build_migrations_info(
            evolver=evolver,
            migration_executor=migration_executor,
            tasks=tasks)
        graph = cls._build_evolutions_graph(
            evolver=evolver,
            migration_executor=migration_executor,
            migrations_info=migrations_info,
            tasks=tasks)
        batches = cls._build_batches(
            evolver=evolver,
            graph=graph,
            hinted=hinted)

        # Set some state that execute_tasks() and unit tests can get to.
        evolver._evolve_app_task_state = {
            # These are used for the execution stage.
            'batches': batches,
            'full_migration_plan': migrations_info.get('full_plan'),
            'migration_executor': migration_executor,
            'pre_migrate_state': migrations_info.get('pre_migrate_state'),

            # These are just stored for the benefit of unit tests.
            'post_migration_plan': migrations_info.get('post_plan'),
            'post_migration_targets': migrations_info.get('post_targets'),
            'pre_migration_plan': migrations_info.get('pre_plan'),
            'pre_migration_targets': migrations_info.get('pre_targets'),
        }

        clear_global_custom_migrations()

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
        state = evolver._evolve_app_task_state
        batches = state['batches']
        full_migration_plan = state['full_migration_plan']
        migrate_state = state['pre_migrate_state']
        migration_executor = state['migration_executor']

        migrating = full_migration_plan is not None
        new_models = list(itertools.chain.from_iterable(
            task.new_models
            for task in tasks
        ))

        if migrating:
            # If we have any applied migration names we wanted to record, do it
            # before we begin any migrations.
            applied_migrations = \
                state['migration_executor'].loader.extra_applied_migrations

            if applied_migrations:
                record_applied_migrations(connection=evolver.connection,
                                          migrations=applied_migrations)

        # Let any listeners know that we're beginning the process.
        emit_pre_migrate_or_sync(verbosity=evolver.verbosity,
                                 interactive=evolver.interactive,
                                 database_name=evolver.database_name,
                                 create_models=new_models,
                                 pre_migrate_state=migrate_state,
                                 plan=full_migration_plan)

        if migrating and migrate_state:
            migrate_state = migrate_state.clone()

        deferred_sql = []

        for batch_info in batches:
            batch_type = batch_info['type']

            if batch_type == UpgradeMethod.EVOLUTIONS:
                # We have evolutions and/or model creations to apply.
                with evolver.sql_executor(check_constraints=False) as \
                        sql_executor:
                    new_models_sql = batch_info.get('new_models_sql')

                    if new_models_sql:
                        deferred_sql += batch_info['new_models_deferred_sql']
                        cls._create_models(
                            sql_executor=sql_executor,
                            evolver=evolver,
                            tasks=batch_info['new_models_tasks'],
                            sql=new_models_sql)

                    # Process any evolutions for the apps.
                    task_evolutions = batch_info.get('task_evolutions', {})

                    for task, task_info in six.iteritems(task_evolutions):
                        task_sql = task_info.get('sql')

                        if task_sql:
                            task.execute(sql_executor=sql_executor,
                                         sql=task_sql,
                                         **kwargs)
            elif batch_type == UpgradeMethod.MIGRATIONS:
                assert migrating

                # We have a batch of migrations to apply.
                migrate_state = apply_migrations(
                    executor=migration_executor,
                    targets=batch_info['migration_targets'],
                    plan=batch_info['migration_plan'],
                    pre_migrate_state=migrate_state)
            else:
                # This should never be reached.
                raise ValueError(
                    '%s is not a valid type for a batch! This should never '
                    'have happened. Please file a bug or contact support.'
                    % batch_type)

        if migrating:
            finalize_migrations(migrate_state)

            # Write the new lists of applied migrations out to the signature.
            applied_migrations = \
                MigrationList.from_database(evolver.connection)
            project_sig = evolver.project_sig

            for app_label in applied_migrations.get_app_labels():
                app_sig = project_sig.get_app_sig(app_label)

                if app_sig is not None:
                    # The signature will take care of storing only the
                    # migrations that apply to it when we assign this.
                    app_sig.applied_migrations = applied_migrations

        # Let any listeners know that we've finished the process.
        emit_post_migrate_or_sync(verbosity=evolver.verbosity,
                                  interactive=evolver.interactive,
                                  database_name=evolver.database_name,
                                  created_models=new_models,
                                  post_migrate_state=migrate_state,
                                  plan=full_migration_plan)

        # Apply any deferred new model SQL.
        if deferred_sql:
            with evolver.sql_executor() as sql_executor:
                EvolveAppTask._apply_deferred_sql(
                    sql_executor=sql_executor,
                    evolver=evolver,
                    sql=deferred_sql)

    @classmethod
    def _build_migration_executor(cls, evolver, tasks):
        """Return a MigrationExecutor for loading and executing migrations.

        The executor is responsible for loading any migrations from disk and
        from the database, along with any custom migrations passed in when
        constructing a :py:class:`EvolveAppTask`, along with validating the
        dependencies and later applying migrations.

        If migration support is not available in the version of Django, this
        will return ``None`` instead.

        Args:
            evolver (Evolver):
                The evolver executing the tasks.

            tasks (list of EvolveAppTask):
                The list of tasks that were prepared.

        Returns:
            django_evolution.utils.migrations.MigrationExecutor:
            The resulting migration executor, or ``None`` if using a version
            of Django without migrations support.

        Raises:
            django_evolution.errors.BaseMigrationError:
                There was an error with the setup or validation of migrations.
                A subclass containing additional details will be raised.
        """
        if not supports_migrations:
            return None

        migration_executor = MigrationExecutor(
            connection=evolver.connection,
            signal_sender=evolver)
        migration_executor.run_checks()

        return migration_executor

    @classmethod
    def _build_migrations_info(cls, evolver, migration_executor, tasks):
        """Build information on the migrations to perform.

        This will construct three migration plans:

        1. A full plan (a beginning-to-end migration, like Django would
           normally apply).
        2. A "pre"-stage plan (any and all initial migrations that would
           set up models for the first time).
        3. A "post"-stage plan (all remaining migrations).

        The pre and post plans are used to bookend a list of evolutions.
        The pre plan will create the initial models, allowing evolutions to
        operate on them (which may have been constructed to modify models
        introduced prior to Django's migrations). The post plan can then
        be run once an evolution moves the app to migrations.

        This will also calculate initial migration state to update when
        migrations are later run, calculated lists of migration targets
        (primarily for unit testing), and information on migrations that are
        or will be marked as applied.

        If migrations are not supported on this version of Django, this will
        return an empty dictionary.

        Args:
            evolver (Evolver):
                The evolver executing the tasks.

            migration_executor (django_evolution.utils.migrations.
                                MigrationExecutor):
                The migration executor that was constructed for these tasks.

            tasks (list of EvolveAppTask):
                The list of tasks that were prepared.

        Returns:
            dict:
            Calculated state for the migrations.

            If migrations are supported, then this will contain the following
            at a minimum:

            ``pre_migrate_state`` (:py:class:`django.db.migrations.state.ProjectState`):
                The migration state before any new migrations are applied.
                Executed migrations will update this state, and the state will
                be passed in any Django signal emissions.

            If migrations are to be executed, then this will also contain:

            ``full_plan`` (list of tuple):
                The full migration plan.

            ``to_mark_applied`` (:py:class:`~django_evolution.utils.migrations.MigrationList):
                A list of migrations that should be marked as applied in the
                migration graph.

            ``post_plan`` (list of tuple):
                The post stage migration plan.

            ``post_targets`` (list of tuple):
                The post stage migration targets. These are the desired
                migrations that a plan is built from.

            ``pre_plan`` (list of tuple):
                The pre stage migration plan.

            ``pre_targets`` (list of tuple):
                The pre stage migration targets. These are the desired
                migrations that a plan is built from.

            If migrations aren't supported on this version of Django, the
            dictionary will be empty.

        Raises:
            django_evolution.errors.BaseMigrationError:
                There was an error with the setup or validation of migrations.
                A subclass containing additional details will be raised.
        """
        if not supports_migrations:
            return {}

        assert migration_executor is not None

        pre_migration_plan = None
        pre_migration_targets = None
        post_migration_plan = None
        post_migration_targets = None

        # Now that we have updated signatures from any evolutions (which
        # may have applied MoveToDjangoMigrations mutators), we can start
        # to figure out the migration plan.
        migration_loader = migration_executor.loader
        extra_applied_migrations = migration_loader.extra_applied_migrations
        assert not extra_applied_migrations

        migrations_to_mark_applied = MigrationList()
        applied_migrations = MigrationList.from_database(evolver.connection)
        migration_app_labels = set()

        if applied_migrations:
            migrations_to_mark_applied.update(applied_migrations)

        # Run through the new applied migrations marked in any app
        # signatures and find any that we're planning to record.
        for task in tasks:
            if (task.app_sig is not None and
                task.upgrade_method == UpgradeMethod.MIGRATIONS):
                migration_app_labels.add(task.app_label)

                if task.applied_migrations:
                    # Figure out which applied migrations the mutator or
                    # signature listed that we don't have in the database.
                    new_applied_migrations = (task.applied_migrations -
                                              applied_migrations)

                    if new_applied_migrations:
                        # We found some. Mark them as being applied. We'll
                        # record them during the execution phase.
                        extra_applied_migrations.update(new_applied_migrations)

        if extra_applied_migrations:
            migrations_to_mark_applied.update(extra_applied_migrations)

        if migration_app_labels:
            if extra_applied_migrations:
                # Rebuild the migration graph, based on anything we've
                # added to extra_applied_migrations above (which is a local
                # reference to the variable on MigrationLoader), and re-run
                # checks.
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

            pre_migrate_state = create_pre_migrate_state(migration_executor)

            # Next, try to find all the initial migrations. These will
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
                pre_migration_targets = filter_migration_targets(
                    targets=pre_migration_targets,
                    app_labels=migration_app_labels,
                    exclude=excluded_targets)

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

                if pre_migration_plan:
                    # Filter this to include only those items not in
                    # pre_migration_plan
                    pre_migration_plan_set = set(pre_migration_plan)
                    post_migration_plan = [
                        plan_item
                        for plan_item in post_migration_plan
                        if plan_item not in pre_migration_plan_set
                    ]
        else:
            # We may not be migrating, but we still want this state
            # for signal emissions, so create it now.
            pre_migrate_state = create_pre_migrate_state(migration_executor)

        # If we don't have anything to do, then all we'll need to set is
        # pre_migrate_state, since we'll still want it for signal emissions.
        result = {
            'pre_migrate_state': pre_migrate_state,
        }

        if not pre_migration_plan:
            pre_migration_plan = None
            pre_migration_targets = None

        if not post_migration_plan:
            post_migration_plan = None
            post_migration_targets = None

        if pre_migration_plan or post_migration_plan:
            result.update({
                'full_plan': full_migration_plan,
                'to_mark_applied': migrations_to_mark_applied,
                'post_plan': post_migration_plan,
                'post_targets': post_migration_targets,
                'pre_plan': pre_migration_plan,
                'pre_targets': pre_migration_targets,
            })

        return result

    @classmethod
    def _build_evolutions_graph(cls, evolver, migration_executor,
                                migrations_info, tasks):
        """Return an EvolutionGraph covering all migrations and evolutions.

        The resulting graph will reflect the dependency relationships between
        all migrations and evolutions that Django Evolution will apply,
        allowing the database operations to be executed in the correct order.

        This will have a loose default ordering of:

        1. Pre-stage migrations
        2. Per-app evolutions in task order
        3. Post-stage migrations

        That mirrors the behavior of Django Evolution 2.0. Any dependencies
        specified by migrations and evolutions will alter this order.

        Args:
            evolver (Evolver):
                The evolver executing the tasks.

            migration_executor (django_evolution.utils.migrations.
                                MigrationExecutor):
                The migration executor that was constructed for these tasks.

            migrations_info (dict):
                Calculated migration information from
                :py:meth:`_build_migrations_info`.

            tasks (list of EvolveAppTask):
                The list of tasks that were prepared.

        Returns:
            django_evolution.utils.graph.EvolutionGraph:
            The resulting evolution graph.
        """
        # Build the dependency graph of evolutions and migrations. This will
        # give us an order in which changes should be applied.
        graph = EvolutionGraph()
        database_name = evolver.database_name

        if migration_executor is not None:
            migration_loader = migration_executor.loader
        else:
            migration_loader = None

        # First, add in the pre-stage migration plan from Django. These will
        # consist of the 0001_initial migrations, creating models that might
        # be needed/referenced by any models managed by Django Evolution or
        # post-stage migrations.
        pre_migration_plan = migrations_info.get('pre_plan')

        if pre_migration_plan:
            graph.add_migration_plan(pre_migration_plan,
                                     migration_loader.graph)

        # Next, the evolutions. All new evolutions for an app will depend on
        # each other by default.
        #
        # An evolution may also depend on another migration or another
        # evolution.
        for task in tasks:
            if task.evolution_required:
                # The task may have prepared new models or evolutions to track,
                # but we may not want to add them to the graph at this stage.
                # Models should only be added if we know we're responsible for
                # generating their SQL, and evolutions should only be added if
                # the app is going to be set up using evolutions instead of
                # migrations.
                if task._new_models_sql:
                    new_models = task.new_models
                else:
                    new_models = []

                if task.hinted_evolution is not None:
                    new_evolutions = [task.hinted_evolution]
                elif task.new_evolutions:
                    new_evolutions = task.new_evolutions
                else:
                    new_evolutions = []

                if new_evolutions or new_models:
                    graph.add_evolutions(
                        app=task.app,
                        evolutions=new_evolutions,
                        new_models=new_models,
                        custom_evolutions=task._evolutions,
                        extra_state={
                            'task': task,
                        })

        # Now that the evolutions are added, add the post-stage migrations.
        # These will be any migrations that either build upon an initial
        # migration or add new content to an app formerly managed by an
        # evolution.
        post_migration_plan = migrations_info.get('post_plan')

        if post_migration_plan:
            graph.add_migration_plan(post_migration_plan,
                                     migration_loader.graph)

        # Everything is added, and dependencies are formed. Some of those
        # dependencies may reference evolutions or migrations in the graph
        # that we haven't added (ones that were already previously applied).
        # Remove those dependencies by telling the graph which migrations we
        # have applied.
        migrations_to_mark_applied = migrations_info.get('to_mark_applied')

        if migrations_to_mark_applied:
            graph.mark_migrations_applied(migrations_to_mark_applied)

        for task in tasks:
            applied_evolutions = get_applied_evolutions(task.app,
                                                        database=database_name)

            if applied_evolutions:
                graph.mark_evolutions_applied(task.app, applied_evolutions)

        # The graph is built! Finalize it (which will check that all
        # dependencies are valid) so we can begin converting it into batches
        # of operations.
        graph.finalize()

        return graph

    @classmethod
    def _build_batches(cls, evolver, graph, hinted):
        """Return batches of evolution/migration operations to execute.

        This takes the order of migrations, evolutions, and model creations
        from an evolution graph and converts it into batches of sequential
        operations that can be performed in :py:meth:`execute_tasks`.

        Each resulting batch will represent either a migration or an
        evolution.

        If a batch represents an evolution, it will contain the following keys:

        ``new_models_sql`` (list, optional):
            The complete, optimized list of SQL statements to execute to
            create models for this batch.

            This will only be present if there are models to create.

        ``new_models_tasks`` (list of EvolveAppTask):
            The list of tasks that generated the SQL.

            This will only be present if there are models to create.

        ``task_evolutions`` (dict):
            A dictionary mapping a :py:class:`EvolveAppTask` instance to
            a dictionary of information containing:

            ``evolutions`` (list of unicode, optional):
                A list of evolution labels being added for that task.

            ``mutations`` (list of :py:class:`~django_evolution.mutations.BaseMutation, optional):
                The optimized list of mutations being run.

            ``sql`` (list):
                The optimized SQL generated from the mutations.

        ``type`` (unicode):
            This will be set to :py:attr:`UpgradeMethod.EVOLUTIONS
            <django_evolution.consts.UpgradeMethod.EVOLUTIONS>`.

        If a batch represents a migration, it will contain the following keys:

        ``migration_plan`` (list of tuple):
            The migration plan for the batch.

        ``migration_targets`` (list of tuple):
            The migration targets for the batch.

        ``type`` (unicode):
            This will be set to :py:attr:`UpgradeMethod.MIGRATIONS
            <django_evolution.consvts.UpgradeMethod.MIGRATIONS>`.

        Args:
            evolver (Evolver):
                The evolver executing the tasks.

            graph (django_evolution.utils.graph.EvolutionGraph):
                The finalized evolution graph.

            hinted (bool):
                Whether a hinted evolution was requested.

        Returns:
            list of dict:
            The list of batches.
        """
        database_name = evolver.database_name

        # Now we'll need to iterate through the batches from the graph and
        # start building more consolidated batches of operations to perform.
        # Any adjancent model creations/evolutions will be converted into a
        # single EVOLUTIONS batch, anad adjacent migrations will be
        # converted into a single MIGRATIONS batch.
        batches = []
        prev_batch_type = None
        prev_batch_info = None

        for node_batch_type, batch_nodes in graph.iter_batches():
            batch_info = {}
            batch_type = None

            if node_batch_type == graph.NODE_TYPE_CREATE_MODEL:
                # This batch creates one or more models. Store the list of
                # new models and the SQL for creating them.
                #
                # This will always be the start of a new batch. It cannot
                # merge into a preceding evolutions batch.
                batch_type = UpgradeMethod.EVOLUTIONS
                batch_info = {
                    'new_models': [
                        node.state['model']
                        for node in batch_nodes
                    ],
                    'new_models_nodes': batch_nodes,
                }
            elif node_batch_type == graph.NODE_TYPE_EVOLUTION:
                # This batch applies new evolutions. Store the list of tasks
                # and their corresponding evolutions.
                task_evolutions = OrderedDict()

                for node in batch_nodes:
                    task = node.state['task']
                    evolution = node.state['evolution']

                    task_info = task_evolutions.setdefault(task, {})
                    task_info.setdefault('evolutions', []).append(
                        evolution.label)

                batch_type = UpgradeMethod.EVOLUTIONS
                batch_info = {
                    'task_evolutions': task_evolutions,
                }
            elif node_batch_type == graph.NODE_TYPE_MIGRATION:
                # This batch applies new migrations. Store the plan and
                # targets.
                #
                # We shouldn't receive two consecutive migration batches, so
                # check for that.
                assert prev_batch_type != UpgradeMethod.MIGRATIONS

                migration_plan = []
                migration_targets = []

                for node in batch_nodes:
                    migration_plan.append(node.state['migration_plan_item'])
                    migration_targets.append(node.state['migration_target'])

                batch_type = UpgradeMethod.MIGRATIONS
                batch_info = {
                    'migration_plan': migration_plan,
                    'migration_targets': migration_targets,
                }
            else:
                # This should never be reached.
                raise ValueError(
                    '%s is not a valid type for a batch! This should never '
                    'have happened. Please file a bug or contact support.'
                    % batch_type)

            # Now that we have new information, let's put this into a batch.
            assert batch_info is not None
            assert batch_type is not None

            if batch_type == prev_batch_type:
                # We're updating the previous batch.
                #
                # We'll need to merge the new information into the existing
                # batch, recursively.
                assert prev_batch_info is not None

                merge_dicts(prev_batch_info, batch_info)
            else:
                # We have a new batch. Set the type and add it to the list of
                # batches.
                batch_info['type'] = batch_type
                batches.append(batch_info)

                prev_batch_info = batch_info
                prev_batch_type = batch_type

        # Now let's perform one last pass, this time through the new
        # consolidated batches. That information will be used to generate
        # the SQL and combined state needed during the execute_tasks() and
        # execute() stages.
        if hinted:
            hinted_evolution = evolver.initial_diff.evolution()
        else:
            hinted_evolution = None

        for batch_info in batches:
            if batch_info['type'] == UpgradeMethod.EVOLUTIONS:
                new_models = batch_info.pop('new_models', None)

                if new_models:
                    # We can now calculate the SQL for all these models.
                    #
                    # We'll also need to grab each unique task in order. For
                    # that, use an OrderedDict's keys, simulating an ordered
                    # set.
                    new_models_nodes = batch_info.pop('new_models_nodes')
                    assert new_models_nodes

                    new_models_sql, new_models_deferred_sql = \
                        sql_create_models(new_models,
                                          db_name=database_name,
                                          return_deferred=True)

                    batch_info.update({
                        'new_models_sql': new_models_sql,
                        'new_models_deferred_sql': new_models_deferred_sql,
                        'new_models_tasks': filter_dup_list_items(
                            node.state['task']
                            for node in new_models_nodes
                        ),
                    })

                # For each task introducing evolutions to apply, we need to
                # determine the pending mutations and resulting SQL for
                # applying those mutations. Since we have a whole batch that
                # we know we'll be applying at once, we can safely optimize
                # those at this stage.
                #
                # Note that we'll have one task per app to evolve.
                task_evolutions = batch_info.get('task_evolutions', {})

                for (batch_task,
                     batch_task_info) in six.iteritems(task_evolutions):
                    # This is going to look pretty similar to what's already
                    # been done in the prepare() stage, and it is. The
                    # difference is that we're now running operations on the
                    # batch's set of evolutions rather than the task's.
                    #
                    # There's not much we can do to share this logic between
                    # here and prepare().
                    if batch_task._evolutions:
                        # Custom evolutions were passed to the task. Build the
                        # list of mutations for all evolutions in this task
                        # in the correct order.
                        mutations_map = {
                            _info['label']: _info['mutations']
                            for _info in batch_task._evolutions
                        }

                        pending_mutations = list(itertools.chain.from_iterable(
                            mutations_map[_label]
                            for _label in batch_task_info['evolutions']
                        ))
                    elif hinted:
                        # This is a hinted mutation, so grab the mutations
                        # hinted for this task's app.
                        pending_mutations = \
                            hinted_evolution.get(batch_task.app_label)
                    else:
                        # This is our standard case: An actual evolution from
                        # written evolution files. Generate the set of
                        # mutations to apply for all queued evolutions in
                        # this task.
                        pending_mutations = get_app_pending_mutations(
                            app=batch_task.app,
                            evolution_labels=batch_task_info['evolutions'],
                            old_project_sig=evolver.project_sig,
                            project_sig=evolver.target_project_sig,
                            database=database_name)

                    if pending_mutations:
                        # We have pending mutations for this task. Generate
                        # the final optimized SQL and list of mutations and
                        # store them for later execution.
                        #
                        # This will modify the signature in the Evolver.
                        mutations_info = batch_task.generate_mutations_info(
                            pending_mutations)

                        if mutations_info:
                            batch_task_info.update({
                                'mutations': mutations_info['mutations'],
                                'sql': mutations_info['sql'],
                            })

        return batches

    @classmethod
    def _create_models(cls, sql_executor, evolver, tasks, sql):
        """Create tables for models in the database.

        Args:
            sql_executor (django_evolution.utils.sql.SQLExecutor):
                The SQL executor used to run any SQL on the database.

            evolver (Evolver):
                The evolver executing the tasks.

            tasks (list of EvolveAppTask):
                The list of tasks containing models to create.

            sql (list):
                The list of SQL statements to execute.

        Returns:
            list:
            The list of SQL statements used to create the model. This is
            used primarily for unit tests.

        Raises:
            django_evolution.errors.EvolutionExecutionError:
                There was an unexpected error creating database models.
        """
        assert sql_executor
        assert tasks
        assert sql

        # We need to create all models at once, in order to allow Django to
        # handle deferring SQL statements referencing a model until after the
        # model has been created.
        #
        # Because of this, we also need to emit the creating_models and
        # created_models signals for every set of models up-front.
        for task in tasks:
            assert task

            creating_models.send(sender=evolver,
                                 app_label=task.app_label,
                                 model_names=task.new_model_names)

        try:
            result = sql_executor.run_sql(sql=sql,
                                          execute=True,
                                          capture=True)
        except Exception as e:
            last_sql_statement = getattr(e, 'last_sql_statement', None)
            detailed_error = six.text_type(e)

            if len(tasks) == 1:
                app_label = tasks[0].app_label

                raise EvolutionExecutionError(
                    _('Error creating database models for %s: %s')
                    % (app_label, e),
                    app_label=app_label,
                    detailed_error=detailed_error,
                    last_sql_statement=last_sql_statement)
            else:
                raise EvolutionExecutionError(
                    _('Error creating database models: %s') % e,
                    detailed_error=detailed_error,
                    last_sql_statement=last_sql_statement)

        for task in tasks:
            created_models.send(sender=evolver,
                                app_label=task.app_label,
                                model_names=task.new_model_names)

        return result

    @classmethod
    def _apply_deferred_sql(cls, sql_executor, evolver, sql):
        """Create tables for models in the database.

        Args:
            sql_executor (django_evolution.utils.sql.SQLExecutor):
                The SQL executor used to run any SQL on the database.

            evolver (Evolver):
                The evolver executing the tasks.

            sql (list):
                The list of SQL statements to execute.

        Returns:
            list:
            The list of SQL statements used to create the model. This is
            used primarily for unit tests.

        Raises:
            django_evolution.errors.EvolutionExecutionError:
                There was an unexpected error creating database models.
        """
        assert sql_executor
        assert sql

        try:
            return sql_executor.run_sql(sql=sql,
                                        execute=True,
                                        capture=True)
        except Exception as e:
            raise EvolutionExecutionError(
                _('Error applying deferred SQL for new database models: %s')
                % e,
                detailed_error=six.text_type(e),
                last_sql_statement=getattr(e, 'last_sql_statement', None))

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
        self.app_sig_is_new = False
        self.new_model_names = []
        self.new_models = []
        self.upgrade_method = None
        self.applied_migrations = None
        self.hinted_evolution = None

        self._new_models_sql = []
        self._new_models_deferred_sql = []
        self._evolutions = evolutions
        self._migrations = migrations
        self._mutations = None
        self._pending_mutations = None

    def generate_mutations_info(self, pending_mutations, update_evolver=True):
        """Generate information on a series of mutations.

        This will optimize and run the list of pending mutations against the
        evolver's stored signature and return the optimized list of mutations
        and SQL, along with some information on the app.

        The evolver's signature will be updated by default, but this can be
        disabled in order to just retrieve information without making any
        changes.

        Args:
            pending_mutations (list of
                               django_evolution.mutations.BaseMutation):
                The list of pending mutations to run.

            update_evolver (bool, optional):
                Whether to update the evolver's signature.

        Returns:
            dict:
            The resulting information from running the mutations. This
            includes the following:

            ``app_mutator`` (:py:class:`~django_evolution.mutations.AppMutator`):
                The app mutator that ran the mutations.

            ``applied_migrations`` (list of tuple):
                The list of migrations that were ultimately marked as applied.

            ``mutations`` (list of :py:class:`~django_evolution.mutations.BaseMutation`):
                The optimized list of mutations.

            ``sql`` (list):
                The optimized list of SQL statements to execute.

            ``upgrade_method`` (unicode):
                The resulting upgrade method for the app, after applying all
                mutations.

            If there are no mutations to run after optimization, this will
            return ``None``.
        """
        mutations = [
            mutation
            for mutation in pending_mutations
            if self.is_mutation_mutable(mutation,
                                        app_label=self.app_label)
        ]

        if not mutations:
            return None

        app_label = self.app_label
        legacy_app_label = self.legacy_app_label

        app_mutator = AppMutator.from_evolver(
            evolver=self.evolver,
            app_label=app_label,
            legacy_app_label=legacy_app_label,
            update_evolver=update_evolver)
        app_mutator.run_mutations(mutations)

        project_sig = app_mutator.project_sig
        app_sig = (
            project_sig.get_app_sig(app_label) or
            project_sig.get_app_sig(legacy_app_label)
        )

        if app_sig is None:
            # The evolutions didn't make any changes to an existing app
            # signature. We may not have had an existing one. Bail.
            applied_migrations = []
            upgrade_method = None
        else:
            applied_migrations = app_sig.applied_migrations
            upgrade_method = app_sig.upgrade_method

        return {
            'app_mutator': app_mutator,
            'applied_migrations': applied_migrations,
            'mutations': mutations,
            'sql': app_mutator.to_sql(),
            'upgrade_method': upgrade_method,
        }

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
        self.app_sig_is_new = app_sig_is_new

        orig_upgrade_method = None
        upgrade_method = None

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
                orig_upgrade_method = app_sig.upgrade_method

            app_upgrade_info = get_app_upgrade_info(app,
                                                    simulate_applied=True,
                                                    database=database_name)
            upgrade_method = app_upgrade_info.get('upgrade_method')
            evolutions = get_evolution_sequence(app)
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
                    pending_mutations = hinted_evolution.get(app_label,
                                                             [])

                    self.hinted_evolution = Evolution(app_label=app_label,
                                                      label='__hinted__')
                else:
                    evolutions = get_unapplied_evolutions(
                        app=app,
                        database=database_name)
                    pending_mutations = get_app_pending_mutations(
                        app=app,
                        evolution_labels=evolutions,
                        database=database_name)

                self._pending_mutations = pending_mutations

                mutations_info = self.generate_mutations_info(
                    pending_mutations,
                    update_evolver=False)

                if mutations_info:
                    app_mutator = mutations_info['app_mutator']
                    self.can_simulate = app_mutator.can_simulate
                    self.sql = mutations_info['sql']
                    self.evolution_required = True
                    self._mutations = mutations_info['mutations']

                    self.applied_migrations = MigrationList.from_names(
                        app_label,
                        mutations_info['applied_migrations'])
                    upgrade_method = mutations_info['upgrade_method']

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

                # This is only going to be directly used if
                # execute(create_models_now=True) is called. Normally,
                # EvolveAppTask._new_models_sql will be used instead. We
                # don't know which way this will be called, so we need both.
                self._new_models_sql, self._new_models_deferred_sql = \
                    sql_create_models(new_models,
                                      db_name=database_name,
                                      return_deferred=True)

        self.upgrade_method = upgrade_method or orig_upgrade_method

        self.app_sig = app_sig
        self.new_evolutions = [
            Evolution(app_label=app_label,
                      label=label)
            for label in evolutions
        ]

    def execute(self, cursor=None, sql_executor=None, sql=None,
                evolutions=None, create_models_now=False):
        """Execute the task.

        This will apply any evolutions queued up for the app.

        Before the evolutions are applied for the app, the
        :py:data:`~django_evolution.signals.applying_evolution` signal will
        be emitted. After,
        :py:data:`~django_evolution.signals.applied_evolution` will be emitted.

        Version Changed:
            2.1:
            * Added ``sql`` and ``evolutions`` arguments.
            * Deprecated ``cursor`` in favor of ``sql_executor``.

        Args:
            cursor (django.db.backends.util.CursorWrapper, unused):
                The legacy database cursor. This is no longer used.

            sql_executor (django_evolution.utils.sql.SQLExecutor):
                The SQL executor used to run any SQL on the database.

            sql (list, optional):
                A list of explicit SQL statements to execute.

                This will override :py:attr:`sql` if provided.

            evolutions (list of django_evolution.models.Evolution, optional):
                A list of evolutions being applied. These will be sent in the
                :py:data:`~django_evolution.signals.applying_evolution` and
                :py:data:`~django_evolution.signals.applied_evolution` signals.

                This will override :py:attr:`new_evolutions` if provided.

            create_models_now (bool, optional):
                Whether to create models as part of this execution. Normally,
                this is handled in :py:meth:`execute_tasks`, but this flag
                allows for more fine-grained control of table creation in
                limited circumstances (intended only by :py:class:`Evolver`).

        Raises:
            django_evolution.errors.EvolutionExecutionError:
                The evolution task failed. Details are in the error.
        """
        assert sql_executor

        evolver = self.evolver

        if create_models_now and self._new_models_sql:
            EvolveAppTask._create_models(
                sql_executor=sql_executor,
                evolver=evolver,
                sql=self._new_models_sql,
                tasks=[self])

            if self._new_models_deferred_sql:
                EvolveAppTask._apply_deferred_sql(
                    sql_executor=sql_executor,
                    evolver=evolver,
                    sql=self._new_models_deferred_sql)

        if evolutions is None:
            evolutions = self.new_evolutions

        if sql is None:
            sql = self.sql

        if sql:
            applying_evolution.send(sender=evolver,
                                    task=self,
                                    evolutions=evolutions)

            try:
                sql_executor.run_sql(sql, execute=True)
            except Exception as e:
                raise EvolutionExecutionError(
                    _('Error applying evolution for %s: %s')
                    % (self.app_label, e),
                    app_label=self.app_label,
                    detailed_error=six.text_type(e),
                    last_sql_statement=getattr(e, 'last_sql_statement'))

            applied_evolution.send(sender=evolver,
                                   task=self,
                                   evolutions=evolutions)

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

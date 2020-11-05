"""Unit tests for django_evolution.evolve.Evolver and related classes."""

from __future__ import unicode_literals

from collections import OrderedDict

from django.db import DEFAULT_DB_ALIAS, models

try:
    # Django >= 1.7
    from django.db import migrations
except ImportError:
    # Django < 1.7
    migrations = None

from django_evolution.compat import six
from django_evolution.compat.apps import (get_app,
                                          get_apps,
                                          register_app_models)
from django_evolution.compat.db import sql_create_app, sql_delete
from django_evolution.consts import UpgradeMethod
from django_evolution.db.state import DatabaseState
from django_evolution.errors import (EvolutionTaskAlreadyQueuedError,
                                     QueueEvolverTaskError)
from django_evolution.evolve import (BaseEvolutionTask, EvolveAppTask,
                                     Evolver, PurgeAppTask)
from django_evolution.models import Evolution, Version
from django_evolution.mutations import (AddField, ChangeField,
                                        MoveToDjangoMigrations)
from django_evolution.signals import (applied_evolution,
                                      applied_migration,
                                      applying_evolution,
                                      applying_migration,
                                      created_models,
                                      creating_models)
from django_evolution.signature import AppSignature, ModelSignature
from django_evolution.support import supports_migrations
from django_evolution.tests import models as evo_test
from django_evolution.tests.evolutions_app import models as test_app2
from django_evolution.tests.base_test_case import (EvolutionTestCase,
                                                   MigrationsTestsMixin)
from django_evolution.tests.decorators import requires_migrations
from django_evolution.tests.evolutions_app.models import EvolutionsAppTestModel
from django_evolution.tests.evolutions_app2.models import (
    EvolutionsApp2TestModel,
    EvolutionsApp2TestModel2)
from django_evolution.tests.migrations_app.models import MigrationsAppTestModel
from django_evolution.tests.migrations_app2.models import \
    MigrationsApp2TestModel
from django_evolution.tests.models import BaseTestModel
from django_evolution.tests.utils import (ensure_test_db,
                                          execute_test_sql,
                                          register_models,
                                          replace_models)
from django_evolution.utils.apps import get_app_label
from django_evolution.utils.migrations import (MigrationList,
                                               record_applied_migrations)


class DummyTask(BaseEvolutionTask):
    def prepare(self, **kwargs):
        pass

    def execute(self):
        pass

    def get_evolution_content(self):
        return None

    def __str__(self):
        return 'Dummy Task'


class EvolverTestModel(BaseTestModel):
    value = models.CharField(max_length=100)


class BaseEvolverTestCase(EvolutionTestCase):
    """Base test case for Evolver-based tests."""

    default_base_model = EvolverTestModel
    sql_mapping_key = 'evolver'
    needs_evolution_models = True


class EvolverTests(BaseEvolverTestCase):
    """Unit tests for django_evolution.evolve.Evolver."""

    def test_init(self):
        """Testing Evolver.__init__"""
        self.assertEqual(Version.objects.count(), 1)
        version = Version.objects.get()

        evolver = Evolver()
        self.assertEqual(evolver.project_sig, version.signature)
        self.assertTrue(evolver.initial_diff.is_empty())
        self.assertEqual(list(evolver.tasks), [])

    def test_init_with_no_baseline(self):
        """Testing Evolver.__init__ with no baseline signatures"""
        Version.objects.all().delete()

        Evolver()

        version = Version.objects.get()
        app_sigs = list(version.signature.app_sigs)
        self.assertEqual(len(app_sigs), 1)
        self.assertEqual(app_sigs[0].app_id, 'django_evolution')

    def test_init_with_no_base_models(self):
        """Testing Evolver.__init__ with no base models"""
        execute_test_sql(sql_delete(get_app('django_evolution')))

        # Make sure these are really gone.
        state = DatabaseState(db_name='default')
        self.assertFalse(state.has_model(Version))

        # Create the new Evolver, which will re-create the tables.
        Evolver()

        version = Version.objects.get()
        app_sigs = list(version.signature.app_sigs)
        self.assertEqual(len(app_sigs), 1)
        self.assertEqual(app_sigs[0].app_id, 'django_evolution')

    def test_can_simulate_with_all_can_simulate_true_evolution_true(self):
        """Testing Evolver.can_simulate with all tasks having can_simulate=True
        """
        evolver = Evolver()

        task1 = DummyTask('dummy1', evolver)
        task1.can_simulate = True
        task1.evolution_required = True
        evolver.queue_task(task1)

        task2 = DummyTask('dummy2', evolver)
        task2.can_simulate = True
        task2.evolution_required = True
        evolver.queue_task(task2)

        self.assertTrue(evolver.can_simulate())

    def test_can_simulate_with_any_can_simulate_true(self):
        """Testing Evolver.can_simulate with any tasks having
        can_simulate=False
        """
        evolver = Evolver()

        task1 = DummyTask('dummy1', evolver)
        task1.can_simulate = True
        task1.evolution_required = True
        evolver.queue_task(task1)

        task2 = DummyTask('dummy2', evolver)
        task2.can_simulate = False
        task2.evolution_required = True
        evolver.queue_task(task2)

        self.assertFalse(evolver.can_simulate())

    def test_can_simulate_with_all_evolution_required_false(self):
        """Testing Evolver.can_simulate with all tasks having
        evolution_required=False
        """
        evolver = Evolver()

        task1 = DummyTask('dummy1', evolver)
        task1.can_simulate = False
        task1.evolution_required = False
        evolver.queue_task(task1)

        task2 = DummyTask('dummy2', evolver)
        task2.can_simulate = False
        task2.evolution_required = False
        evolver.queue_task(task2)

        self.assertTrue(evolver.can_simulate())

    def test_can_simulate_with_any_evolution_required_false(self):
        """Testing Evolver.can_simulate with any tasks having
        evolution_required=True
        """
        evolver = Evolver()

        task1 = DummyTask('dummy1', evolver)
        task1.can_simulate = False
        task1.evolution_required = False
        evolver.queue_task(task1)

        task2 = DummyTask('dummy2', evolver)
        task2.can_simulate = False
        task2.evolution_required = True
        evolver.queue_task(task2)

        self.assertFalse(evolver.can_simulate())

    def test_get_evolution_required_with_all_true(self):
        """Testing Evolver.get_evolution_required with all tasks having
        evolution_required=False
        """
        evolver = Evolver()

        task1 = DummyTask('dummy1', evolver)
        task1.evolution_required = False
        evolver.queue_task(task1)

        task2 = DummyTask('dummy2', evolver)
        task2.evolution_required = True
        evolver.queue_task(task2)

        self.assertFalse(evolver.can_simulate())

    def test_get_evolution_required_with_any_true(self):
        """Testing Evolver.get_evolution_required with any tasks having
        evolution_required=True
        """
        evolver = Evolver()

        task1 = DummyTask('dummy1', evolver)
        task1.evolution_required = False
        evolver.queue_task(task1)

        task2 = DummyTask('dummy2', evolver)
        task2.evolution_required = True
        evolver.queue_task(task2)

        self.assertFalse(evolver.can_simulate())

    def test_diff_evolutions(self):
        """Testing Evolver.diff_evolutions"""
        version = Version.objects.current_version()
        model_sig = (
            version.signature
            .get_app_sig('django_evolution')
            .get_model_sig('Evolution')
        )
        model_sig.get_field_sig('label').field_attrs['max_length'] = 50
        version.save()

        evolver = Evolver()
        evolver.queue_evolve_all_apps()

        diff = evolver.diff_evolutions()
        self.assertFalse(diff.is_empty())

        self.assertEqual(
            diff.changed,
            {
                'django_evolution': {
                    'changed': {
                        'Evolution': {
                            'changed': {
                                'label': ['max_length'],
                            },
                        },
                    },
                },
            })

    def test_diff_evolutions_with_hinted_true(self):
        """Testing Evolver.diff_evolutions with hinting"""
        version = Version.objects.current_version()
        model_sig = (
            version.signature
            .get_app_sig('django_evolution')
            .get_model_sig('Evolution')
        )
        model_sig.get_field_sig('label').field_attrs['max_length'] = 50
        version.save()

        evolver = Evolver(hinted=True)
        evolver.queue_evolve_all_apps()

        diff = evolver.diff_evolutions()
        self.assertTrue(diff.is_empty())

    def test_iter_evolution_content(self):
        """Testing Evolver.iter_evolution_content"""
        version = Version.objects.current_version()
        model_sig = (
            version.signature
            .get_app_sig('django_evolution')
            .get_model_sig('Evolution')
        )
        model_sig.get_field_sig('label').field_attrs['max_length'] = 50
        version.save()

        evolver = Evolver(hinted=True)
        evolver.queue_evolve_all_apps()
        evolver.queue_task(DummyTask('dummy', evolver))

        content = list(evolver.iter_evolution_content())
        self.assertEqual(len(content), 1)
        self.assertIsInstance(content[0][0], EvolveAppTask)
        self.assertEqual(
            content[0][1],
            "from __future__ import unicode_literals\n"
            "\n"
            "from django_evolution.mutations import ChangeField\n"
            "\n"
            "\n"
            "MUTATIONS = [\n"
            "    ChangeField('Evolution', 'label', initial=None,"
            " max_length=100),\n"
            "]")

    def test_queue_evolve_app(self):
        """Testing Evolver.queue_evolve_app"""
        app = get_app('django_evolution')

        evolver = Evolver()
        evolver.queue_evolve_app(app)

        tasks = list(evolver.tasks)
        self.assertEqual(len(tasks), 1)
        self.assertIsInstance(tasks[0], EvolveAppTask)
        self.assertIs(tasks[0].app, app)

    def test_queue_evolve_app_with_already_queued(self):
        """Testing Evolver.queue_evolve_app with app already queued"""
        app = get_app('django_evolution')

        evolver = Evolver()
        evolver.queue_evolve_app(app)

        message = '"django_evolution" is already being tracked for evolution'

        with self.assertRaisesMessage(EvolutionTaskAlreadyQueuedError,
                                      message):
            evolver.queue_evolve_app(app)

    def test_queue_evolve_app_after_prepared(self):
        """Testing Evolver.queue_evolve_app after tasks were already prepared
        """
        evolver = Evolver()

        # Force preparation of tasks.
        list(evolver.tasks)

        message = (
            'Evolution tasks have already been prepared. New tasks '
            'cannot be added.'
        )

        with self.assertRaisesMessage(QueueEvolverTaskError, message):
            evolver.queue_evolve_app(get_app('django_evolution'))

    def test_queue_evolve_all_apps(self):
        """Testing Evolver.queue_evolve_all_apps"""
        evolver = Evolver()
        evolver.queue_evolve_all_apps()

        apps = get_apps()
        tasks = list(evolver.tasks)

        self.assertGreater(len(apps), 0)
        self.assertEqual(len(tasks), len(apps))

        for app, task in zip(apps, tasks):
            self.assertIsInstance(task, EvolveAppTask)
            self.assertIs(task.app, app)

    def test_queue_evolve_all_apps_with_app_already_queued(self):
        """Testing Evolver.queue_evolve_all_apps with app already queued"""
        evolver = Evolver()
        evolver.queue_evolve_app(get_app('django_evolution'))

        message = '"django_evolution" is already being tracked for evolution'

        with self.assertRaisesMessage(EvolutionTaskAlreadyQueuedError,
                                      message):
            evolver.queue_evolve_all_apps()

    def test_queue_evolve_all_apps_after_prepared(self):
        """Testing Evolver.queue_evolve_all_apps after tasks were already
        prepared
        """
        evolver = Evolver()

        # Force preparation of tasks.
        list(evolver.tasks)

        message = (
            'Evolution tasks have already been prepared. New tasks '
            'cannot be added.'
        )

        with self.assertRaisesMessage(QueueEvolverTaskError, message):
            evolver.queue_evolve_all_apps()

    def test_queue_purge_app(self):
        """Testing Evolver.queue_purge_app"""
        version = Version.objects.current_version()
        version.signature.add_app_sig(AppSignature(app_id='old_app'))
        version.save()

        evolver = Evolver()
        evolver.queue_purge_app('old_app')

        tasks = list(evolver.tasks)
        self.assertEqual(len(tasks), 1)
        self.assertIsInstance(tasks[0], PurgeAppTask)
        self.assertEqual(tasks[0].app_label, 'old_app')

    def test_queue_purge_app_with_already_queued(self):
        """Testing Evolver.queue_purge_app with app purge already queued"""
        version = Version.objects.current_version()
        version.signature.add_app_sig(AppSignature(app_id='old_app'))
        version.save()

        evolver = Evolver()
        evolver.queue_purge_app('old_app')

        message = '"old_app" is already being tracked for purging'

        with self.assertRaisesMessage(EvolutionTaskAlreadyQueuedError,
                                      message):
            evolver.queue_purge_app('old_app')

    def test_queue_purge_app_after_prepared(self):
        """Testing Evolver.queue_purge_app after tasks were already prepared"""
        version = Version.objects.current_version()
        version.signature.add_app_sig(AppSignature(app_id='old_app'))
        version.save()

        evolver = Evolver()

        # Force preparation of tasks.
        list(evolver.tasks)

        message = (
            'Evolution tasks have already been prepared. New tasks '
            'cannot be added.'
        )

        with self.assertRaisesMessage(QueueEvolverTaskError, message):
            evolver.queue_purge_app('old_app')

    def test_queue_purge_old_apps(self):
        """Testing Evolver.queue_purge_old_apps"""
        version = Version.objects.current_version()
        version.signature.add_app_sig(AppSignature(app_id='old_app1'))
        version.signature.add_app_sig(AppSignature(app_id='old_app2'))
        version.save()

        evolver = Evolver()
        evolver.queue_purge_old_apps()

        tasks = list(evolver.tasks)
        self.assertEqual(len(tasks), 2)
        self.assertIsInstance(tasks[0], PurgeAppTask)
        self.assertIsInstance(tasks[1], PurgeAppTask)
        self.assertEqual(tasks[0].app_label, 'old_app1')
        self.assertEqual(tasks[1].app_label, 'old_app2')

    def test_queue_purge_old_apps_without_old_apps(self):
        """Testing Evolver.queue_purge_old_apps without old apps"""
        evolver = Evolver()
        evolver.queue_purge_old_apps()

        self.assertEqual(list(evolver.tasks), [])

    def test_queue_purge_old_apps_with_already_queued(self):
        """Testing Evolver.queue_purge_old_apps with app purge already queued
        """
        version = Version.objects.current_version()
        version.signature.add_app_sig(AppSignature(app_id='old_app1'))
        version.save()

        evolver = Evolver()
        evolver.queue_purge_app('old_app1')

        message = '"old_app1" is already being tracked for purging'

        with self.assertRaisesMessage(EvolutionTaskAlreadyQueuedError,
                                      message):
            evolver.queue_purge_old_apps()

    def test_queue_purge_old_apps_after_prepared(self):
        """Testing Evolver.queue_purge_old_apps after tasks were already
        prepared
        """
        version = Version.objects.current_version()
        version.signature.add_app_sig(AppSignature(app_id='old_app1'))
        version.save()

        evolver = Evolver()

        # Force preparation of tasks.
        list(evolver.tasks)

        message = (
            'Evolution tasks have already been prepared. New tasks '
            'cannot be added.'
        )

        with self.assertRaisesMessage(QueueEvolverTaskError, message):
            evolver.queue_purge_old_apps()

    def test_evolve(self):
        """Testing Evolver.evolve"""
        model_sig = ModelSignature.from_model(EvolverTestModel)
        model_sig.get_field_sig('value').field_attrs['max_length'] = 50

        app_sig = AppSignature(app_id='tests')
        app_sig.add_model_sig(model_sig)

        orig_version = Version.objects.current_version()
        orig_version.signature.add_app_sig(app_sig)
        orig_version.save()

        with ensure_test_db(model_entries=[('TestModel', EvolverTestModel)]):
            evolver = Evolver()
            evolver.queue_task(EvolveAppTask(
                evolver=evolver,
                app=evo_test,
                evolutions=[
                    {
                        'label': 'my_evolution1',
                        'mutations': [
                            ChangeField('TestModel', 'value', max_length=200),
                        ],
                    },
                    {
                        'label': 'my_evolution2',
                        'mutations': [
                            AddField('TestModel', 'new_field',
                                     models.BooleanField, null=True),
                        ],
                    },
                ]))
            evolver.evolve()

        self.assertTrue(evolver.evolved)

        version = Version.objects.current_version()
        self.assertNotEqual(version, orig_version)
        self.assertFalse(version.is_hinted())

        self.assertAppliedEvolutions(
            [
                ('tests', 'my_evolution1'),
                ('tests', 'my_evolution2'),
            ],
            version=version)

        model_sig = (
            version.signature
            .get_app_sig('tests')
            .get_model_sig('TestModel')
        )
        self.assertEqual(
            model_sig.get_field_sig('value').field_attrs['max_length'],
            200)
        self.assertIsNotNone(model_sig.get_field_sig('new_field'))

    def test_evolve_with_hinted(self):
        """Testing Evolver.evolve with hinting"""
        model_sig = ModelSignature.from_model(EvolverTestModel)
        model_sig.get_field_sig('value').field_attrs['max_length'] = 50

        app_sig = AppSignature(app_id='tests')
        app_sig.add_model_sig(model_sig)

        orig_version = Version.objects.current_version()
        orig_version.signature.add_app_sig(app_sig)
        orig_version.save()

        with ensure_test_db(model_entries=[('TestModel', EvolverTestModel)]):
            evolver = Evolver(hinted=True)
            evolver.queue_evolve_app(evo_test)
            evolver.evolve()

        self.assertTrue(evolver.evolved)

        version = Version.objects.current_version()
        self.assertNotEqual(version, orig_version)
        self.assertTrue(version.is_hinted())

        model_sig = (
            version.signature
            .get_app_sig('tests')
            .get_model_sig('TestModel')
        )
        self.assertEqual(
            model_sig.get_field_sig('value').field_attrs['max_length'],
            100)


class EvolveAppTaskTests(MigrationsTestsMixin, BaseEvolverTestCase):
    """Unit tests for django_evolution.evolve.EvolveAppTask."""

    def setUp(self):
        super(EvolveAppTaskTests, self).setUp()

        model_sig = ModelSignature.from_model(EvolverTestModel)
        model_sig.get_field_sig('value').field_attrs['max_length'] = 50

        app_sig = AppSignature(app_id='tests')
        app_sig.add_model_sig(model_sig)

        version = Version.objects.current_version()
        version.signature.add_app_sig(app_sig)
        version.save()

        self.version = version
        self.app_sig = app_sig

        self.saw_signals = []
        applying_evolution.connect(self._on_applying_evolution)
        applied_evolution.connect(self._on_applied_evolution)
        applying_migration.connect(self._on_applying_migration)
        applied_migration.connect(self._on_applied_migration)
        creating_models.connect(self._on_creating_models)
        created_models.connect(self._on_created_models)

    def tearDown(self):
        super(EvolveAppTaskTests, self).tearDown()

        applying_evolution.disconnect(self._on_applying_evolution)
        applied_evolution.disconnect(self._on_applied_evolution)
        applying_migration.disconnect(self._on_applying_migration)
        applied_migration.disconnect(self._on_applied_migration)
        creating_models.disconnect(self._on_creating_models)
        created_models.disconnect(self._on_created_models)

    @requires_migrations
    def test_prepare_tasks_with_migrations_new_app(self):
        """Testing EvolveAppTask.prepare_tasks with migrations for new
        app
        """
        class MigrationTestModel(BaseTestModel):
            field1 = models.IntegerField()
            field3 = models.BooleanField()

        class InitialMigration(migrations.Migration):
            operations = [
                migrations.CreateModel(
                    name='MigrationTestModel',
                    fields=[
                        ('id', models.AutoField(verbose_name='ID',
                                                serialize=False,
                                                auto_created=True,
                                                primary_key=True)),
                        ('field1', models.IntegerField()),
                        ('field2', models.CharField(max_length=10)),
                    ]
                ),
            ]

        class AddFieldMigration(migrations.Migration):
            dependencies = [
                ('tests', '0001_initial'),
            ]

            operations = [
                migrations.AddField(
                    model_name='MigrationTestModel',
                    name='field3',
                    field=models.BooleanField()),
            ]

        class RemoveFieldMigration(migrations.Migration):
            dependencies = [
                ('tests', '0002_add_field'),
            ]

            operations = [
                migrations.RemoveField(
                    model_name='MigrationTestModel',
                    name='field2'),
            ]

        register_app_models('tests',
                            [('MigrationTestModel', MigrationTestModel)],
                            reset=True)

        evolver = Evolver()
        evolver.project_sig.get_app_sig('tests').upgrade_method = \
            UpgradeMethod.MIGRATIONS

        app_migrations = [
            InitialMigration('0001_initial', 'tests'),
            AddFieldMigration('0002_add_field', 'tests'),
            RemoveFieldMigration('0003_remove_field', 'tests'),
        ]

        task = EvolveAppTask(evolver=evolver,
                             app=evo_test,
                             migrations=app_migrations)
        evolver.queue_task(task)

        EvolveAppTask.prepare_tasks(evolver, [task])

        state = evolver._evolve_app_task_state
        self.assertIsNotNone(state['migration_executor'])

        self._check_migration_plan(
            state['pre_migration_plan'],
            [
                ('tests', '0001_initial', False),
            ])
        self._check_migration_plan(
            state['post_migration_plan'],
            [
                ('tests', '0002_add_field', False),
                ('tests', '0003_remove_field', False),
            ])
        self.assertEqual(
            state['pre_migration_targets'],
            [
                ('tests', '0001_initial'),
            ])
        self.assertEqual(
            state['post_migration_targets'],
            [
                ('tests', '0003_remove_field'),
            ])

        # Check the batches.
        batches = state['batches']
        self.assertEqual(len(batches), 1)

        self._check_migration_batch(
            batches[0],
            expected_migration_plan=[
                ('tests', '0001_initial', False),
                ('tests', '0002_add_field', False),
                ('tests', '0003_remove_field', False),
            ],
            expected_migration_targets=[
                ('tests', '0001_initial'),
                ('tests', '0002_add_field'),
                ('tests', '0003_remove_field'),
            ])

    @requires_migrations
    def test_prepare_tasks_with_migrations_some_applied(self):
        """Testing EvolveAppTask.prepare_tasks with migrations and some
        already applied
        """
        class MigrationTestModel(BaseTestModel):
            field1 = models.IntegerField()
            field3 = models.BooleanField()

        class InitialMigration(migrations.Migration):
            operations = [
                migrations.CreateModel(
                    name='MigrationTestModel',
                    fields=[
                        ('id', models.AutoField(verbose_name='ID',
                                                serialize=False,
                                                auto_created=True,
                                                primary_key=True)),
                        ('field1', models.IntegerField()),
                        ('field2', models.CharField(max_length=10)),
                    ]
                ),
            ]

        class AddFieldMigration(migrations.Migration):
            dependencies = [
                ('tests', '0001_initial'),
            ]

            operations = [
                migrations.AddField(
                    model_name='MigrationTestModel',
                    name='field3',
                    field=models.BooleanField()),
            ]

        class RemoveFieldMigration(migrations.Migration):
            dependencies = [
                ('tests', '0002_add_field'),
            ]

            operations = [
                migrations.RemoveField(
                    model_name='MigrationTestModel',
                    name='field2'),
            ]

        register_app_models('tests',
                            [('MigrationTestModel', MigrationTestModel)],
                            reset=True)

        evolver = Evolver()
        evolver.project_sig.get_app_sig('tests').upgrade_method = \
            UpgradeMethod.MIGRATIONS

        migration_list = MigrationList()
        migration_list.add_migration_info(app_label='tests',
                                          name='0001_initial')

        record_applied_migrations(connection=evolver.connection,
                                  migrations=migration_list)

        app_migrations = [
            InitialMigration('0001_initial', 'tests'),
            AddFieldMigration('0002_add_field', 'tests'),
            RemoveFieldMigration('0003_remove_field', 'tests'),
        ]

        task = EvolveAppTask(evolver=evolver,
                             app=evo_test,
                             migrations=app_migrations)
        evolver.queue_task(task)

        EvolveAppTask.prepare_tasks(evolver, [task])
        state = evolver._evolve_app_task_state

        self.assertIsNotNone(state['migration_executor'])
        self.assertIsNone(state['pre_migration_plan'])
        self.assertIsNone(state['pre_migration_targets'])

        self._check_migration_plan(
            state['post_migration_plan'],
            [
                ('tests', '0002_add_field', False),
                ('tests', '0003_remove_field', False),
            ])
        self.assertEqual(
            state['post_migration_targets'],
            [
                ('tests', '0003_remove_field'),
            ])

        # Check the batches.
        batches = state['batches']
        self.assertEqual(len(batches), 1)

        self._check_migration_batch(
            batches[0],
            expected_migration_plan=[
                ('tests', '0002_add_field', False),
                ('tests', '0003_remove_field', False),
            ],
            expected_migration_targets=[
                ('tests', '0002_add_field'),
                ('tests', '0003_remove_field'),
            ])

    def test_prepare_tasks_with_dependencies_and_new_db(self):
        """Testing EvolveAppTask.prepare_tasks with complex dependencies and
        new database
        """
        self.ensure_deleted_apps()

        evolver = Evolver()
        tasks = self._get_test_apps_tasks(evolver)
        EvolveAppTask.prepare_tasks(evolver, tasks)

        state = evolver._evolve_app_task_state

        # Make sure we've collected the evolutions we expect. See
        # _get_test_apps() for the order.
        self.assertEvolutionsEqual(
            tasks[0].new_evolutions,
            [
                ('evolutions_app', 'first_evolution'),
                ('evolutions_app', 'second_evolution'),
            ])
        self.assertEvolutionsEqual(
            tasks[1].new_evolutions,
            [
                ('evolutions_app2', 'test_evolution'),
            ])
        self.assertEvolutionsEqual(
            tasks[2].new_evolutions,
            [
                ('evolution_deps_app', 'test_evolution'),
            ])

        if supports_migrations:
            self.assertEqual(tasks[3].new_evolutions, [])
            self.assertEqual(tasks[4].new_evolutions, [])
            self.assertIsNotNone(state['migration_executor'])
        else:
            self.assertIsNone(state['migration_executor'])

        if supports_migrations:
            self._check_migration_plan(
                state['pre_migration_plan'],
                [
                    ('migrations_app', '0001_initial', False),
                    ('migrations_app', '0002_add_field', False),
                    ('migrations_app2', '0001_initial', False),
                ])
            self.assertEqual(
                state['pre_migration_targets'],
                [
                    ('migrations_app', '0001_initial'),
                    ('migrations_app2', '0001_initial'),
                ])
            self._check_migration_plan(
                state['post_migration_plan'],
                [
                    ('migrations_app2', '0002_add_field', False),
                ])
            self.assertEqual(
                state['post_migration_targets'],
                [
                    ('migrations_app', '0002_add_field'),
                    ('migrations_app2', '0002_add_field'),
                ])
        else:
            self.assertIsNone(state['pre_migration_plan'])
            self.assertIsNone(state['pre_migration_targets'])
            self.assertIsNone(state['post_migration_plan'])
            self.assertIsNone(state['post_migration_targets'])

        # Check the batches.
        batches = state['batches']

        if supports_migrations:
            self.assertEqual(len(batches), 3)
        else:
            self.assertEqual(len(batches), 1)

        batches = iter(batches)

        # Batch 1.
        if supports_migrations:
            self._check_migration_batch(
                next(batches),
                expected_migration_plan=[
                    ('migrations_app', '0001_initial', False),
                ],
                expected_migration_targets=[
                    ('migrations_app', '0001_initial'),
                ])

        # Batch 2.
        self._check_evolution_batch(
            next(batches),
            expected_new_models_sql='complex_deps_new_db_new_models',
            expected_new_models_tasks=[tasks[1], tasks[0]],
            expected_task_evolutions=OrderedDict([
                (tasks[1], {
                    'evolutions': ['test_evolution'],
                }),
                (tasks[0], {
                    'evolutions': ['first_evolution', 'second_evolution'],
                }),
            ]))

        # Batch 3.
        if supports_migrations:
            self._check_migration_batch(
                next(batches),
                expected_migration_plan=[
                    ('migrations_app', '0002_add_field', False),
                    ('migrations_app2', '0001_initial', False),
                    ('migrations_app2', '0002_add_field', False),
                ],
                expected_migration_targets=[
                    ('migrations_app', '0002_add_field'),
                    ('migrations_app2', '0001_initial'),
                    ('migrations_app2', '0002_add_field'),
                ])

    def test_prepare_tasks_with_dependencies_and_upgrade_db(self):
        """Testing EvolveAppTask.prepare_tasks with complex dependencies and
        upgrading database
        """
        self._setup_pre_upgrade()

        evolver = Evolver()
        tasks = self._get_test_apps_tasks(evolver)
        EvolveAppTask.prepare_tasks(evolver, tasks)

        state = evolver._evolve_app_task_state

        # Make sure we've collected the evolutions we expect. See
        # _get_test_apps() for the order.
        self.assertEvolutionsEqual(
            tasks[0].new_evolutions,
            [
                ('evolutions_app', 'second_evolution'),
            ])
        self.assertEvolutionsEqual(
            tasks[1].new_evolutions,
            [
                ('evolutions_app2', 'test_evolution'),
            ])
        self.assertEvolutionsEqual(
            tasks[2].new_evolutions,
            [
                ('evolution_deps_app', 'test_evolution'),
            ])

        if supports_migrations:
            self.assertEqual(tasks[3].new_evolutions, [])
            self.assertEqual(tasks[4].new_evolutions, [])
            self.assertIsNotNone(state['migration_executor'])
        else:
            self.assertIsNone(state['migration_executor'])

        if supports_migrations:
            self._check_migration_plan(
                state['pre_migration_plan'],
                [
                    ('migrations_app', '0002_add_field', False),
                    ('migrations_app2', '0001_initial', False),
                ])
            self.assertEqual(
                state['pre_migration_targets'],
                [
                    ('migrations_app2', '0001_initial'),
                ])
            self._check_migration_plan(
                state['post_migration_plan'],
                [
                    ('migrations_app2', '0002_add_field', False),
                ])
            self.assertEqual(
                state['post_migration_targets'],
                [
                    ('migrations_app', '0002_add_field'),
                    ('migrations_app2', '0002_add_field'),
                ])
        else:
            self.assertIsNone(state['pre_migration_plan'])
            self.assertIsNone(state['pre_migration_targets'])
            self.assertIsNone(state['post_migration_plan'])
            self.assertIsNone(state['post_migration_targets'])

        # Check the batches.
        batches = state['batches']

        if supports_migrations:
            self.assertEqual(len(batches), 2)
        else:
            self.assertEqual(len(batches), 1)

        batches = iter(batches)

        # Batch 1.
        self._check_evolution_batch(
            next(batches),
            expected_task_evolutions=OrderedDict([
                (tasks[1], {
                    'evolutions': ['test_evolution'],
                    'mutations': [
                        AddField('EvolutionsApp2TestModel', 'fkey',
                                 models.ForeignKey, null=True,
                                 related_model=('evolutions_app.'
                                                'EvolutionsAppTestModel')),
                    ],
                    'sql': 'complex_deps_upgrade_task_2',
                }),
                (tasks[0], {
                    'evolutions': ['second_evolution'],
                    'mutations': [
                        ChangeField('EvolutionsAppTestModel',
                                    'char_field',
                                    max_length=10,
                                    null=True),
                        ChangeField('EvolutionsAppTestModel',
                                    'char_field2',
                                    max_length=20,
                                    null=True),
                    ],
                    'sql': 'complex_deps_upgrade_task_1',
                }),
            ]))

        # Batch 2.
        if supports_migrations:
            self._check_migration_batch(
                next(batches),
                expected_migration_plan=[
                    ('migrations_app', '0002_add_field', False),
                    ('migrations_app2', '0001_initial', False),
                    ('migrations_app2', '0002_add_field', False),
                ],
                expected_migration_targets=[
                    ('migrations_app', '0002_add_field'),
                    ('migrations_app2', '0001_initial'),
                    ('migrations_app2', '0002_add_field'),
                ])

    @requires_migrations
    def test_execute_tasks_with_migrations(self):
        """Testing EvolveAppTask.execute_tasks with migrations"""
        class MigrationTestModel(BaseTestModel):
            field1 = models.IntegerField()
            field2 = models.CharField(max_length=10)
            field3 = models.BooleanField()

        class InitialMigration(migrations.Migration):
            operations = [
                migrations.CreateModel(
                    name='TestModel',
                    fields=[
                        ('id', models.AutoField(verbose_name='ID',
                                                serialize=False,
                                                auto_created=True,
                                                primary_key=True)),
                        ('field1', models.IntegerField()),
                        ('field2', models.CharField(max_length=10)),
                    ]
                ),
            ]

        class AddFieldMigration(migrations.Migration):
            dependencies = [
                ('tests', '0001_initial'),
            ]

            operations = [
                migrations.AddField(
                    model_name='TestModel',
                    name='field3',
                    field=models.BooleanField()),
            ]

        self.set_base_model(MigrationTestModel)

        with ensure_test_db():
            evolver = Evolver()
            evolver.project_sig.get_app_sig('tests').upgrade_method = \
                UpgradeMethod.MIGRATIONS

            # Record some migrations that don't match anything we're evolving,
            # just to make sure nothing blows up.
            migration_list = MigrationList()
            migration_list.add_migration_info(app_label='some_app',
                                              name='0001_initial')
            record_applied_migrations(connection=evolver.connection,
                                      migrations=migration_list)

            app_migrations = [
                InitialMigration('0001_initial', 'tests'),
                AddFieldMigration('0002_add_field', 'tests'),
            ]

            task = EvolveAppTask(evolver=evolver,
                                 app=evo_test,
                                 migrations=app_migrations)
            evolver.queue_task(task)

            EvolveAppTask.prepare_tasks(evolver, [task])
            EvolveAppTask.execute_tasks(evolver, [task])

            self.assertEqual(
                self.saw_signals,
                [
                    ('applying_migration', {
                        'sender': evolver,
                        'migration': ('tests', '0001_initial'),
                    }),
                    ('applied_migration', {
                        'sender': evolver,
                        'migration': ('tests', '0001_initial'),
                    }),
                    ('applying_migration', {
                        'sender': evolver,
                        'migration': ('tests', '0002_add_field'),
                    }),
                    ('applied_migration', {
                        'sender': evolver,
                        'migration': ('tests', '0002_add_field'),
                    }),
                ])

            applied_migrations = \
                MigrationList.from_database(evolver.connection)

            self.assertTrue(applied_migrations.has_migration_info(
                app_label='tests',
                name='0001_initial'))
            self.assertTrue(applied_migrations.has_migration_info(
                app_label='tests',
                name='0002_add_field'))

            # Make sure we can now use the model.
            MigrationTestModel.objects.create(field1=42,
                                              field2='foo',
                                              field3=True)

    @requires_migrations
    def test_execute_tasks_with_evolutions_and_migrations(self):
        """Testing EvolveAppTask.execute_tasks with evolutions and migrations
        """
        class EvolveMigrateTestModel(BaseTestModel):
            field1 = models.IntegerField()

        class FinalTestModel(BaseTestModel):
            field1 = models.IntegerField()
            field2 = models.CharField(max_length=10)
            field3 = models.BooleanField()

            class Meta:
                app_label = 'tests'
                db_table = 'tests_testmodel'

        class InitialMigration(migrations.Migration):
            operations = [
                migrations.CreateModel(
                    name='TestModel',
                    fields=[
                        ('id', models.AutoField(verbose_name='ID',
                                                serialize=False,
                                                auto_created=True,
                                                primary_key=True)),
                        ('field1', models.IntegerField()),
                        ('field2', models.CharField(max_length=10)),
                    ]
                ),
            ]

        class AddFieldMigration(migrations.Migration):
            dependencies = [
                ('tests', '0001_initial'),
            ]

            operations = [
                migrations.AddField(
                    model_name='TestModel',
                    name='field3',
                    field=models.BooleanField()),
            ]

        self.set_base_model(EvolveMigrateTestModel)
        self.app_sig.remove_model_sig('TestModel')
        self.app_sig.add_model_sig(ModelSignature.from_model(
            EvolveMigrateTestModel))
        self.version.save()

        model_entries = [
            ('TestModel', EvolveMigrateTestModel),
        ]

        with ensure_test_db(model_entries=model_entries):
            evolver = Evolver()
            app_sig = evolver.project_sig.get_app_sig('tests')
            app_sig.upgrade_method = UpgradeMethod.EVOLUTIONS
            assert app_sig.get_model_sig('TestModel').get_field_sig('field1')

            app_migrations = [
                InitialMigration('0001_initial', 'tests'),
                AddFieldMigration('0002_add_field', 'tests'),
            ]

            task = EvolveAppTask(
                evolver=evolver,
                app=evo_test,
                evolutions=[
                    {
                        'label': 'add_field2',
                        'mutations': [
                            AddField('TestModel', 'field2',
                                     models.CharField,
                                     max_length=10,
                                     initial=0),
                        ],
                    },
                    {
                        'label': 'move_to_migrations',
                        'mutations': [
                            MoveToDjangoMigrations(
                                mark_applied=['0001_initial']),
                        ],
                    },
                ],
                migrations=app_migrations)

            evolver.queue_task(task)
            EvolveAppTask.prepare_tasks(evolver, [task])
            EvolveAppTask.execute_tasks(evolver, [task])

            # Check that we've seen all the signals we expect.
            self.assertEqual(
                self.saw_signals,
                [
                    ('applying_evolution', {
                        'evolutions': [
                            ('tests', 'add_field2'),
                            ('tests', 'move_to_migrations'),
                        ],
                        'sender': evolver,
                        'task': task,
                    }),
                    ('applied_evolution', {
                        'evolutions': [
                            ('tests', 'add_field2'),
                            ('tests', 'move_to_migrations'),
                        ],
                        'sender': evolver,
                        'task': task,
                    }),
                    ('applying_migration', {
                        'sender': evolver,
                        'migration': ('tests', '0002_add_field'),
                    }),
                    ('applied_migration', {
                        'sender': evolver,
                        'migration': ('tests', '0002_add_field'),
                    }),
                ])

            # Check the app signature for the new state.
            self.assertEqual(app_sig.upgrade_method, UpgradeMethod.MIGRATIONS)
            self.assertEqual(app_sig.applied_migrations,
                             set(['0001_initial', '0002_add_field']))

            # Check that all evolutions were recorded.
            new_evolutions = task.new_evolutions
            self.assertEqual(len(new_evolutions), 2)
            self.assertEqual(new_evolutions[0].label, 'add_field2')
            self.assertEqual(new_evolutions[1].label, 'move_to_migrations')

            # Check that all migrations were recorded.
            applied_migrations = \
                MigrationList.from_database(evolver.connection)

            self.assertTrue(applied_migrations.has_migration_info(
                app_label='tests',
                name='0001_initial'))
            self.assertTrue(applied_migrations.has_migration_info(
                app_label='tests',
                name='0002_add_field'))

            # Make sure we can now use the model.
            self.set_base_model(FinalTestModel)
            FinalTestModel.objects.create(field1=42,
                                          field2='foo',
                                          field3=True)

    def test_execute_tasks_with_dependencies_and_new_db(self):
        """Testing EvolveAppTask.execute_tasks with complex dependencies and
        new database
        """
        self.ensure_deleted_apps()

        evolver = Evolver()
        tasks = self._get_test_apps_tasks(evolver)
        EvolveAppTask.prepare_tasks(evolver, tasks)
        EvolveAppTask.execute_tasks(evolver, tasks)

        # Check that we've seen all the signals we expect.
        expected_signals = []

        if supports_migrations:
            expected_signals += [
                ('applying_migration', {
                    'migration': ('migrations_app', '0001_initial'),
                    'sender': evolver,
                }),
                ('applied_migration', {
                    'migration': ('migrations_app', '0001_initial'),
                    'sender': evolver,
                }),
            ]

        expected_signals += [
            ('creating_models', {
                'app_label': 'evolutions_app2',
                'model_names': [
                    'EvolutionsApp2TestModel',
                    'EvolutionsApp2TestModel2',
                ],
                'sender': evolver,
            }),
            ('creating_models', {
                'app_label': 'evolutions_app',
                'model_names': ['EvolutionsAppTestModel'],
                'sender': evolver,
            }),
            ('created_models', {
                'app_label': 'evolutions_app2',
                'model_names': [
                    'EvolutionsApp2TestModel',
                    'EvolutionsApp2TestModel2',
                ],
                'sender': evolver,
            }),
            ('created_models', {
                'app_label': 'evolutions_app',
                'model_names': ['EvolutionsAppTestModel'],
                'sender': evolver,
            }),
        ]

        if supports_migrations:
            expected_signals += [
                ('applying_migration', {
                    'migration': ('migrations_app', '0002_add_field'),
                    'sender': evolver,
                }),
                ('applied_migration', {
                    'migration': ('migrations_app', '0002_add_field'),
                    'sender': evolver,
                }),
                ('applying_migration', {
                    'migration': ('migrations_app2', '0001_initial'),
                    'sender': evolver,
                }),
                ('applied_migration', {
                    'migration': ('migrations_app2', '0001_initial'),
                    'sender': evolver,
                }),
                ('applying_migration', {
                    'migration': ('migrations_app2', '0002_add_field'),
                    'sender': evolver,
                }),
                ('applied_migration', {
                    'migration': ('migrations_app2', '0002_add_field'),
                    'sender': evolver,
                }),
            ]

        self.assertEqual(self.saw_signals, expected_signals)

        # Make sure all evolutions and migrations are applied.
        if supports_migrations:
            self.assertAppliedMigrations([
                ('migrations_app', '0001_initial'),
                ('migrations_app', '0002_add_field'),
                ('migrations_app2', '0001_initial'),
                ('migrations_app2', '0002_add_field'),
            ])

        # Make sure we can now use the models.
        model1 = EvolutionsAppTestModel.objects.create(char_field='abc123')
        model2 = EvolutionsApp2TestModel.objects.create(char_field='def456',
                                                        fkey=model1)
        EvolutionsApp2TestModel2.objects.create(int_field=42,
                                                fkey=model2)

        if supports_migrations:
            MigrationsAppTestModel.objects.create(char_field='abc123',
                                                  added_field=100)
            MigrationsApp2TestModel.objects.create(char_field='def456',
                                                   added_field=True)

    def test_execute_tasks_with_dependencies_and_upgrade_db(self):
        """Testing EvolveAppTask.execute_tasks with complex dependencies and
        upgrading database
        """
        return
        self._setup_pre_upgrade()

        evolver = Evolver()
        tasks = self._get_test_apps_tasks(evolver)
        EvolveAppTask.prepare_tasks(evolver, tasks)
        EvolveAppTask.execute_tasks(evolver, tasks)

        # Check that we've seen all the signals we expect.
        expected_signals = [
            ('applying_evolution', {
                'evolutions': [
                    ('evolutions_app2', 'test_evolution'),
                ],
                'sender': evolver,
                'task': tasks[1],
            }),
            ('applied_evolution', {
                'evolutions': [
                    ('evolutions_app2', 'test_evolution'),
                ],
                'sender': evolver,
                'task': tasks[1],
            }),
            ('applying_evolution', {
                'evolutions': [
                    ('evolutions_app', 'second_evolution'),
                ],
                'sender': evolver,
                'task': tasks[0],
            }),
            ('applied_evolution', {
                'evolutions': [
                    ('evolutions_app', 'second_evolution'),
                ],
                'sender': evolver,
                'task': tasks[0],
            }),
        ]

        if supports_migrations:
            expected_signals += [
                ('applying_migration', {
                    'migration': ('migrations_app', '0002_add_field'),
                    'sender': evolver,
                }),
                ('applied_migration', {
                    'migration': ('migrations_app', '0002_add_field'),
                    'sender': evolver,
                }),
                ('applying_migration', {
                    'migration': ('migrations_app2', '0001_initial'),
                    'sender': evolver,
                }),
                ('applied_migration', {
                    'migration': ('migrations_app2', '0001_initial'),
                    'sender': evolver,
                }),
                ('applying_migration', {
                    'migration': ('migrations_app2', '0002_add_field'),
                    'sender': evolver,
                }),
                ('applied_migration', {
                    'migration': ('migrations_app2', '0002_add_field'),
                    'sender': evolver,
                }),
            ]

        self.assertEqual(self.saw_signals, expected_signals)

        # Make sure all evolutions and migrations are applied.
        self.assertAppliedMigrations([
            ('migrations_app', '0001_initial'),
            ('migrations_app', '0002_add_field'),
            ('migrations_app2', '0001_initial'),
            ('migrations_app2', '0002_add_field'),
        ])

        # Make sure we can now use the models.
        model1 = EvolutionsAppTestModel.objects.create(char_field='abc123')
        model2 = EvolutionsApp2TestModel.objects.create(char_field='def456',
                                                        fkey=model1)
        EvolutionsApp2TestModel2.objects.create(int_field=42,
                                                fkey=model2)

        if supports_migrations:
            MigrationsAppTestModel.objects.create(char_field='abc123',
                                                  added_field=100)
            MigrationsApp2TestModel.objects.create(char_field='def456',
                                                   added_field=True)

    def test_create_models_with_deferred_refs(self):
        """Testing EvolveAppTask.create_models with deferred refs between
        app-owned models
        """
        # We need evolution-friendly apps we can anchor to.
        app1 = evo_test
        app2 = test_app2
        app_label1 = get_app_label(app1)
        app_label2 = get_app_label(app2)

        # Put the default model from evolutions_app in the database, so it
        # don't appear in the SQL below.
        self.ensure_evolved_apps([app2])

        class ReffedEvolverTestModel(BaseTestModel):
            # Needed in Django 1.6 to ensure the model isn't filtered out
            # in our own get_models() call.
            __module__ = app2.__name__

            value = models.CharField(max_length=100)

            class Meta:
                app_label = app_label2

        class ReffingEvolverTestModel(BaseTestModel):
            value = models.CharField(max_length=100)
            ref = models.ForeignKey(ReffedEvolverTestModel,
                                    on_delete=models.CASCADE)

            class Meta:
                app_label = app_label1

        register_models(
            database_state=self.database_state,
            models=[('ReffedEvolverTestModel', ReffedEvolverTestModel)],
            new_app_label=app_label2,
            db_name=self.default_database_name)

        self.set_base_model(ReffingEvolverTestModel)

        evolver = Evolver()
        task1 = EvolveAppTask(evolver=evolver,
                              app=app1)
        task2 = EvolveAppTask(evolver=evolver,
                              app=app2)

        evolver.queue_task(task1)
        evolver.queue_task(task2)
        EvolveAppTask.prepare_tasks(evolver, [task1, task2])

        state = evolver._evolve_app_task_state

        self.assertEqual(len(state['batches']), 1)
        batch = state['batches'][0]

        with ensure_test_db(app_label=app_label1):
            with ensure_test_db(app_label=app_label2):
                with evolver.sql_executor() as sql_executor:
                    sql = EvolveAppTask._create_models(
                        sql_executor=sql_executor,
                        evolver=evolver,
                        sql=batch['new_models_sql'],
                        tasks=[task1, task2])

        self.assertSQLMappingEqual(sql, 'create_tables_with_deferred_refs')

    def test_prepare_with_hinted_false(self):
        """Testing EvolveAppTask.prepare with hinted=False"""
        register_app_models('tests', [('TestModel', EvolverTestModel)],
                            reset=True)

        with ensure_test_db(model_entries=[('TestModel', EvolverTestModel)]):
            evolver = Evolver()
            task = EvolveAppTask(
                evolver=evolver,
                app=evo_test,
                evolutions=[
                    {
                        'label': 'my_evolution1',
                        'mutations': [
                            ChangeField('TestModel', 'value', max_length=100),
                        ],
                    },
                ])
            task.prepare(hinted=False)

        self.assertTrue(task.evolution_required)
        self.assertTrue(task.can_simulate)
        self.assertSQLMappingEqual(task.sql, 'evolve_app_task')
        self.assertEqual(len(task.new_evolutions), 1)
        self.assertEqual(task.new_models, [])
        self.assertEqual(task.new_model_names, [])
        self.assertEqual(task._new_models_sql, [])

        evolution = task.new_evolutions[0]
        self.assertEqual(evolution.app_label, 'tests')
        self.assertEqual(evolution.label, 'my_evolution1')

    def test_prepare_with_hinted_true(self):
        """Testing EvolveAppTask.prepare with hinted=True"""
        register_app_models('tests', [('TestModel', EvolverTestModel)],
                            reset=True)

        with ensure_test_db(model_entries=[('TestModel', EvolverTestModel)]):
            evolver = Evolver(hinted=True)
            task = EvolveAppTask(evolver=evolver,
                                 app=evo_test)
            task.prepare(hinted=True)

        self.assertTrue(task.evolution_required)
        self.assertTrue(task.can_simulate)
        self.assertSQLMappingEqual(task.sql, 'evolve_app_task')
        self.assertEqual(len(task.new_evolutions), 0)
        self.assertEqual(task.new_models, [])
        self.assertEqual(task.new_model_names, [])
        self.assertEqual(task._new_models_sql, [])

    def test_prepare_with_new_app(self):
        """Testing EvolveAppTask.prepare with new app"""
        register_app_models('tests', [('TestModel', EvolverTestModel)],
                            reset=True)

        evolver = Evolver(hinted=True)
        evolver.project_sig.remove_app_sig('tests')

        task = EvolveAppTask(evolver=evolver,
                             app=evo_test)
        task.prepare(hinted=False)

        self.assertTrue(task.evolution_required)
        self.assertTrue(task.can_simulate)
        self.assertEqual(task.sql, [])
        self.assertEqual(len(task.new_evolutions), 0)
        self.assertEqual(task.new_model_names, ['TestModel'])
        self.assertSQLMappingEqual(task._new_models_sql, 'create_table')

    def test_prepare_with_new_app_no_models(self):
        """Testing EvolveAppTask.prepare with new app and no models"""
        app = get_app('evolution_deps_app')

        register_app_models('evolution_deps_app',
                            model_infos=[],
                            reset=True)

        evolver = Evolver(hinted=True)
        self.assertIsNone(
            evolver.project_sig.get_app_sig('evolution_deps_app'))

        task = EvolveAppTask(evolver=evolver,
                             app=app)
        task.prepare(hinted=False)

        self.assertFalse(task.evolution_required)
        self.assertFalse(task.can_simulate)
        self.assertEqual(task.sql, [])
        self.assertEqual(task.new_model_names, [])
        self.assertEqual(task._new_models_sql, [])

        self.assertEqual(len(task.new_evolutions), 1)

        evolution = task.new_evolutions[0]
        self.assertEqual(evolution.app_label, 'evolution_deps_app')
        self.assertEqual(evolution.label, 'test_evolution')

    def test_prepare_with_new_models(self):
        """Testing EvolveAppTask.prepare with new models"""
        register_app_models('tests', [('TestModel', EvolverTestModel)],
                            reset=True)

        evolver = Evolver(hinted=True)
        evolver.project_sig.get_app_sig('tests').remove_model_sig('TestModel')

        task = EvolveAppTask(evolver=evolver,
                             app=evo_test)
        task.prepare(hinted=False)

        self.assertTrue(task.evolution_required)
        self.assertTrue(task.can_simulate)
        self.assertEqual(task.sql, [])
        self.assertEqual(len(task.new_evolutions), 0)
        self.assertEqual(task.new_model_names, ['TestModel'])
        self.assertSQLMappingEqual(task._new_models_sql, 'create_table')

    def test_execute(self):
        """Testing EvolveAppTask.execute"""
        with ensure_test_db(model_entries=[('TestModel', EvolverTestModel)]):
            evolver = Evolver()
            task = EvolveAppTask(
                evolver=evolver,
                app=evo_test,
                evolutions=[
                    {
                        'label': 'my_evolution1',
                        'mutations': [
                            ChangeField('TestModel', 'value', max_length=100),
                        ],
                    },
                ])
            task.prepare(hinted=False)

            with evolver.sql_executor() as sql_executor:
                task.execute(sql_executor=sql_executor)

        self.assertEqual(
            self.saw_signals,
            [
                ('applying_evolution', {
                    'evolutions': [
                        ('tests', 'my_evolution1'),
                    ],
                    'sender': evolver,
                    'task': task,
                }),
                ('applied_evolution', {
                    'evolutions': [
                        ('tests', 'my_evolution1'),
                    ],
                    'sender': evolver,
                    'task': task,
                }),
            ])

    def test_execute_with_new_models(self):
        """Testing EvolveAppTask.execute with new models and default behavior
        """
        evolver = Evolver()
        evolver.project_sig.remove_app_sig('tests')

        task = EvolveAppTask(evolver=evolver,
                             app=evo_test)
        task.prepare(hinted=False)

        with evolver.sql_executor() as sql_executor:
            task.execute(sql_executor=sql_executor)

        self.assertEqual(self.saw_signals, [])

    def test_execute_with_new_models_and_create_models_now(self):
        """Testing EvolveAppTask.execute with new models and
        create_models_now=True
        """
        evolver = Evolver()
        evolver.project_sig.remove_app_sig('tests')

        with ensure_test_db():
            task = EvolveAppTask(evolver=evolver,
                                 app=evo_test)
            task.prepare(hinted=False)

            with evolver.sql_executor() as sql_executor:
                task.execute(sql_executor=sql_executor,
                             create_models_now=True)

        self.assertEqual(
            self.saw_signals,
            [
                ('creating_models', {
                    'app_label': 'tests',
                    'model_names': ['TestModel'],
                    'sender': evolver,
                }),
                ('created_models', {
                    'app_label': 'tests',
                    'model_names': ['TestModel'],
                    'sender': evolver,
                }),
            ])

    def test_get_evolution_content(self):
        """Testing EvolveAppTask.get_evolution_content"""
        evolver = Evolver()
        task = EvolveAppTask(
            evolver=evolver,
            app=evo_test,
            evolutions=[
                {
                    'label': 'my_evolution1',
                    'mutations': [
                        ChangeField('TestModel', 'value', max_length=100),
                    ],
                },
            ])
        task.prepare(hinted=False)

        content = task.get_evolution_content()
        self.assertEqual(
            content,
            "from __future__ import unicode_literals\n"
            "\n"
            "from django_evolution.mutations import ChangeField\n"
            "\n"
            "\n"
            "MUTATIONS = [\n"
            "    ChangeField('TestModel', 'value', initial=None,"
            " max_length=100),\n"
            "]")

    def _get_test_apps(self):
        """Return a standard list of apps used to test evolutions/migrations.

        Returns:
            list of module:
            The list of test apps.
        """
        apps = [
            get_app('evolutions_app'),
            get_app('evolutions_app2'),
            get_app('evolution_deps_app'),
        ]

        if supports_migrations:
            apps += [
                get_app('migrations_app'),
                get_app('migrations_app2'),
            ]

        return apps

    def _get_test_apps_tasks(self, evolver):
        """Return a standard list of tasks for test evolutions/migrations.

        Returns:
            list of django_evolution.evolve.EvolveAppTask:
            The list of tasks.
        """
        return [
            EvolveAppTask(evolver=evolver,
                          app=app)
            for app in self._get_test_apps()
        ]

    def _setup_pre_upgrade(self):
        """Set up database and signature state before an upgrade test.

        This will register some models that contain a
        pre-evolution/pre-migration schema, store the signature in the
        database as the current verson, and create the matching tables in the
        database. Upgrades can then be performed against the database and
        signature state.
        """
        self.ensure_deleted_apps()

        class InitialEvolutionsAppTestModel(models.Model):
            char_field = models.CharField(max_length=10)
            char_field2 = models.CharField(max_length=20)

            class Meta:
                db_table = EvolutionsAppTestModel._meta.db_table

        class InitialEvolutionsApp2TestModel(models.Model):
            char_field = models.CharField(max_length=10)

            class Meta:
                db_table = EvolutionsApp2TestModel._meta.db_table

        apps_to_models = {
            'evolutions_app': [
                ('EvolutionsAppTestModel', InitialEvolutionsAppTestModel),
            ],
            'evolutions_app2': [
                ('EvolutionsApp2TestModel', InitialEvolutionsApp2TestModel),
                ('EvolutionsApp2TestModel2', EvolutionsApp2TestModel2),
            ],
        }

        version = Version.objects.current_version()
        project_sig = version.signature

        database = DEFAULT_DB_ALIAS
        sql = []

        with replace_models(database_state=self.database_state,
                            apps_to_models=apps_to_models):
            for app in self._get_test_apps():
                project_sig.add_app_sig(AppSignature.from_app(
                    app,
                    database=database))

                sql += sql_create_app(app=app,
                                      db_name=database)

        execute_test_sql(sql,
                         database=database)
        version.save()

        # Record evolutions and migrations in the database that we want to
        # say are applied.
        self.assertFalse(Evolution.objects.exists())
        self.record_evolutions(version,
                               [('evolutions_app', 'first_evolution')])

        if supports_migrations:
            self.record_applied_migrations([
                ('migrations_app', '0001_initial'),
            ])

    def _check_migration_plan(self, migration_plan, expected_items):
        """Check a migration plan for the expected informaton.

        Args:
            migration_plan (list):
                The migration plan to check.

            expected_items (list of tuple):
                A normalized version of a migration plan to compare against
                ``migration_plan``. Each item is a tuple containing:

                1. The app label.
                2. The migration name.
                3. The "reverse" boolean flag.

        Raises:
            AssertionError:
                The migration plan did not match.
        """
        self.assertEqual(
            [
                (migration.app_label, migration.name, reverse)
                for migration, reverse in migration_plan
            ],
            expected_items)

    def _check_evolution_batch(self, batch, expected_task_evolutions=None,
                               expected_new_models_sql=None,
                               expected_new_models_tasks=None):
        """Check an evolution batch for the expected information.

        Args:
            batch (dict):
                The batch item to check.

            expected_task_evolutions (collections.OrderedDict, optional):
                A normalized version of the ``task_evolutions`` data to
                compare. This looks for the following optional keys:

                ``evolutions``:
                    The expected list of evolution labels.

                ``mutations``:
                    The expected list of mutations.

                ``sql_mapping_name``:
                    The SQL mapping name to compare generated SQL against.

            expected_new_models_sql (unicode, optional):
                The SQL mapping name representing the SQL used to create
                new models.

            expected_new_models_tasks (list of
                                       django_evolution.evolve.EvolveAppTask,
                                       optional):
                The list of tasks introducing new models.

        Raises:
            AssertionError:
                One of the batch items did not match.
        """
        self.assertEqual(batch['type'], 'evolutions')

        if expected_new_models_sql is None:
            self.assertNotIn('new_models_sql', batch)
        else:
            self.assertIn('new_models_sql', batch)
            self.assertSQLMappingEqual(batch['new_models_sql'],
                                       expected_new_models_sql,
                                       sql_mappings_key='evolver')

        if expected_new_models_tasks is None:
            self.assertNotIn('new_models_tasks', batch)
        else:
            self.assertIn('new_models_tasks', batch)
            self.assertEqual(batch['new_models_tasks'],
                             expected_new_models_tasks)

        if expected_task_evolutions is None:
            self.assertNotIn('task_evolutions', batch)
        else:
            self.assertIn('task_evolutions', batch)
            batch_task_evolutions = batch['task_evolutions']

            # Order will matter here.
            self.assertEqual(list(six.iterkeys(batch_task_evolutions)),
                             list(six.iterkeys(expected_task_evolutions)))

            for task, info in six.iteritems(expected_task_evolutions):
                batch_task_info = batch_task_evolutions[task]

                if 'evolutions' in info:
                    self.assertIn('evolutions', batch_task_info)
                    self.assertEqual(batch_task_info['evolutions'],
                                     info['evolutions'])
                else:
                    self.assertNotIn('evolutions', batch_task_info)

                if 'mutations' in info:
                    self.assertIn('mutations', batch_task_info)
                    self.assertListEqual(batch_task_info['mutations'],
                                         info['mutations'])
                else:
                    self.assertNotIn('mutations', batch_task_info)

                if 'sql' in info:
                    self.assertIn('sql', batch_task_info)
                    self.assertSQLMappingEqual(batch_task_info['sql'],
                                               info['sql'],
                                               sql_mappings_key='evolver')
                    self.assertEqual(batch_task_info['mutations'],
                                     info['mutations'])
                else:
                    self.assertNotIn('sql', batch_task_info)

    def _check_migration_batch(self, batch, expected_migration_plan,
                               expected_migration_targets):
        """Check a migration batch for the expected informaton.

        Args:
            batch (dict):
                The batch item to check.

            expected_migration_plan (list of tuple):
                A normalized version of a migration plan to compare against
                the batch. Each item is a tuple containing:

                1. The app label.
                2. The migration name.
                3. The "reverse" boolean flag.

            expected_migration_targets (list of tuple):
                A list of migration targets.

        Raises:
            AssertionError:
                One of the batch items did not match.
        """
        self.assertEqual(batch['type'], 'migrations')
        self.assertEqual(batch['migration_targets'],
                         expected_migration_targets)
        self._check_migration_plan(batch['migration_plan'],
                                   expected_migration_plan)

    def _on_applying_evolution(self, sender, task, evolutions, **kwargs):
        """Handle the applying_evolution signal.

        This will store information on the signal emission in
        :py:attr:`saw_signals` for inspection by unit tests.

        Args:
            sender (django_evolution.evolve.Evolver):
                The sender of the signal.

            task (django_evolution.evolve.EvolveAppTask):
                The task that's evolving the app.

            evolutions (list of django_evolution.models.Evolution):
                The list of evolutions that are being applied.

            **kwargs (dict):
                Additional keyword arguments from the signal.
        """
        self.saw_signals.append(('applying_evolution', {
            'sender': sender,
            'task': task,
            'evolutions': [
                (evolution.app_label, evolution.label)
                for evolution in evolutions
            ],
        }))

    def _on_applied_evolution(self, sender, task, evolutions, **kwargs):
        """Handle the applied_evolution signal.

        This will store information on the signal emission in
        :py:attr:`saw_signals` for inspection by unit tests.

        Args:
            sender (django_evolution.evolve.Evolver):
                The sender of the signal.

            task (django_evolution.evolve.EvolveAppTask):
                The task that evolved the app.

            evolutions (list of django_evolution.models.Evolution):
                The list of evolutions that were applied.

            **kwargs (dict):
                Additional keyword arguments from the signal.
        """
        self.saw_signals.append(('applied_evolution', {
            'sender': sender,
            'task': task,
            'evolutions': [
                (evolution.app_label, evolution.label)
                for evolution in evolutions
            ],
        }))

    def _on_applying_migration(self, sender, migration, **kwargs):
        """Handle the applying_migration signal.

        This will store information on the signal emission in
        :py:attr:`saw_signals` for inspection by unit tests.

        Args:
            sender (django_evolution.evolve.Evolver):
                The sender of the signal.

            migration (django.db.migrations.migration.Migration):
                The migration that will be applied.

            **kwargs (dict):
                Additional keyword arguments from the signal.
        """
        self.saw_signals.append(('applying_migration', {
            'sender': sender,
            'migration': (migration.app_label, migration.name),
        }))

    def _on_applied_migration(self, sender, migration, **kwargs):
        """Handle the applied_migration signal.

        This will store information on the signal emission in
        :py:attr:`saw_signals` for inspection by unit tests.

        Args:
            sender (django_evolution.evolve.Evolver):
                The sender of the signal.

            migration (django.db.migrations.migration.Migration):
                The migration that was applied.

            **kwargs (dict):
                Additional keyword arguments from the signal.
        """
        self.saw_signals.append(('applied_migration', {
            'sender': sender,
            'migration': (migration.app_label, migration.name),
        }))

    def _on_creating_models(self, sender, app_label, model_names, **kwargs):
        """Handle the creating_models signal.

        This will store information on the signal emission in
        :py:attr:`saw_signals` for inspection by unit tests.

        Args:
            sender (django_evolution.evolve.Evolver):
                The sender of the signal.

            app_label (unicode):
                The app label the models are associated with.

            model_names (list of unicode):
                The list of model names that are being created.

            **kwargs (dict):
                Additional keyword arguments from the signal.
        """
        self.saw_signals.append(('creating_models', {
            'app_label': app_label,
            'model_names': model_names,
            'sender': sender,
        }))

    def _on_created_models(self, sender, app_label, model_names, **kwargs):
        """Handle the created_models signal.

        This will store information on the signal emission in
        :py:attr:`saw_signals` for inspection by unit tests.

        Args:
            sender (django_evolution.evolve.Evolver):
                The sender of the signal.

            app_label (unicode):
                The app label the models are associated with.

            model_names (list of unicode):
                The list of model names that were created.

            **kwargs (dict):
                Additional keyword arguments from the signal.
        """
        self.saw_signals.append(('created_models', {
            'app_label': app_label,
            'model_names': model_names,
            'sender': sender,
        }))


class PurgeAppTaskTests(BaseEvolverTestCase):
    """Unit tests for django_evolution.evolve.PurgeAppTask."""

    def setUp(self):
        super(PurgeAppTaskTests, self).setUp()

        app_sig = AppSignature(app_id='tests')
        app_sig.add_model_sig(ModelSignature(
            model_name='TestModel',
            table_name='tests_testmodel'))

        version = Version.objects.current_version()
        version.signature.add_app_sig(app_sig)
        version.save()

    def test_prepare(self):
        """Testing PurgeAppTask.prepare"""
        task = PurgeAppTask(evolver=Evolver(),
                            app_label='tests')
        task.prepare()

        self.assertTrue(task.evolution_required)
        self.assertEqual(task.new_evolutions, [])
        self.assertTrue(task.can_simulate)
        self.assertSQLMappingEqual(task.sql, 'purge_app_task')

    def test_execute(self):
        """Testing PurgeAppTask.execute"""
        evolver = Evolver()

        task = PurgeAppTask(evolver=evolver,
                            app_label='tests')
        task.prepare()

        with ensure_test_db(model_entries=[('TestModel', EvolverTestModel)]):
            with evolver.sql_executor() as sql_executor:
                task.execute(sql_executor=sql_executor)

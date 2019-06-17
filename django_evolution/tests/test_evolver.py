"""Unit tests for django_evolution.evolve.Evolver and related classes."""

from __future__ import unicode_literals

from django.db import connections, models
from django.dispatch import receiver

from django_evolution.compat.apps import get_app, get_apps
from django_evolution.errors import (EvolutionBaselineMissingError,
                                     EvolutionTaskAlreadyQueuedError,
                                     QueueEvolverTaskError)
from django_evolution.evolve import (BaseEvolutionTask, EvolveAppTask,
                                     Evolver, PurgeAppTask)
from django_evolution.models import Version
from django_evolution.mutations import AddField, ChangeField
from django_evolution.signals import (applied_evolution,
                                      applying_evolution,
                                      created_models,
                                      creating_models)
from django_evolution.signature import AppSignature, ModelSignature
from django_evolution.tests import models as evo_test
from django_evolution.tests.base_test_case import EvolutionTestCase
from django_evolution.tests.models import BaseTestModel
from django_evolution.tests.utils import ensure_test_db


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
        """Testing Evolver.__init__ with no baselines"""
        Version.objects.all().delete()

        with self.assertRaises(EvolutionBaselineMissingError):
            Evolver()

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

        evolutions = list(version.evolutions.all())
        self.assertEqual(len(evolutions), 2)
        self.assertEqual(evolutions[0].app_label, 'tests')
        self.assertEqual(evolutions[0].label, 'my_evolution1')
        self.assertEqual(evolutions[1].app_label, 'tests')
        self.assertEqual(evolutions[1].label, 'my_evolution2')

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


class EvolveAppTaskTests(BaseEvolverTestCase):
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

        self.saw_signals = set()
        applying_evolution.connect(self._on_applying_evolution)
        applied_evolution.connect(self._on_applied_evolution)
        creating_models.connect(self._on_creating_models)
        created_models.connect(self._on_created_models)

    def tearDown(self):
        super(EvolveAppTaskTests, self).tearDown()

        applying_evolution.disconnect(self._on_applying_evolution)
        applied_evolution.disconnect(self._on_applied_evolution)
        creating_models.disconnect(self._on_creating_models)
        created_models.disconnect(self._on_created_models)

    def test_prepare_with_hinted_false(self):
        """Testing EvolveAppTask.prepare with hinted=False"""
        from django_evolution.compat.apps import register_app_models
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
        self.assertEqual('\n'.join(task.sql),
                         self.get_sql_mapping('evolve_app_task'))
        self.assertEqual(len(task.new_evolutions), 1)
        self.assertEqual(task.new_model_names, [])
        self.assertEqual(task.new_models_sql, [])

        evolution = task.new_evolutions[0]
        self.assertEqual(evolution.app_label, 'tests')
        self.assertEqual(evolution.label, 'my_evolution1')

    def test_prepare_with_hinted_true(self):
        """Testing EvolveAppTask.prepare with hinted=True"""
        from django_evolution.compat.apps import register_app_models
        register_app_models('tests', [('TestModel', EvolverTestModel)],
                            reset=True)

        with ensure_test_db(model_entries=[('TestModel', EvolverTestModel)]):
            evolver = Evolver(hinted=True)
            task = EvolveAppTask(evolver=evolver,
                                 app=evo_test)
            task.prepare(hinted=True)

        self.assertTrue(task.evolution_required)
        self.assertTrue(task.can_simulate)
        self.assertEqual('\n'.join(task.sql),
                         self.get_sql_mapping('evolve_app_task'))
        self.assertEqual(len(task.new_evolutions), 0)
        self.assertEqual(task.new_model_names, [])
        self.assertEqual(task.new_models_sql, [])

    def test_prepare_with_new_app(self):
        """Testing EvolveAppTask.prepare with new app"""
        from django_evolution.compat.apps import register_app_models
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
        self.assertEqual('\n'.join(task.new_models_sql),
                         self.get_sql_mapping('create_table'))

    def test_prepare_with_new_models(self):
        """Testing EvolveAppTask.prepare with new models"""
        from django_evolution.compat.apps import register_app_models
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
        self.assertEqual('\n'.join(task.new_models_sql),
                         self.get_sql_mapping('create_table'))

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
            task.execute(connections['default'].cursor())

        self.assertEqual(self.saw_signals, set(['applying_evolution',
                                                'applied_evolution']))

    def test_execute_with_new_models(self):
        """Testing EvolveAppTask.execute with new models and default behavior
        """
        evolver = Evolver()
        evolver.project_sig.remove_app_sig('tests')

        task = EvolveAppTask(evolver=evolver,
                             app=evo_test)
        task.prepare(hinted=False)
        task.execute(connections['default'].cursor())

        self.assertEqual(self.saw_signals, set())

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
            task.execute(connections['default'].cursor(),
                         create_models_now=True)

        self.assertEqual(self.saw_signals, set(['creating_models',
                                                'created_models']))

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

    def _on_applying_evolution(self, **kwargs):
        self.saw_signals.add('applying_evolution')

    def _on_applied_evolution(self, **kwargs):
        self.saw_signals.add('applied_evolution')

    def _on_creating_models(self, **kwargs):
        self.saw_signals.add('creating_models')

    def _on_created_models(self, **kwargs):
        self.saw_signals.add('created_models')


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
        self.assertEqual('\n'.join(task.sql),
                         self.get_sql_mapping('purge_app_task'))

    def test_execute(self):
        """Testing PurgeAppTask.execute"""
        task = PurgeAppTask(evolver=Evolver(),
                            app_label='tests')
        task.prepare()

        with ensure_test_db(model_entries=[('TestModel', EvolverTestModel)]):
            task.execute(connections['default'].cursor())

"""Unit tests for django_evolution.utils.migrations."""

from __future__ import unicode_literals

from django.db import DEFAULT_DB_ALIAS, connections, models

try:
    # Django >= 1.7
    from django.db import migrations
    from django.db.migrations.recorder import MigrationRecorder
except ImportError:
    # Django < 1.7
    MigrationRecorder = None
    migrations = None

from django_evolution.compat.apps import get_app
from django_evolution.db.state import DatabaseState
from django_evolution.errors import (MigrationConflictsError,
                                     MigrationHistoryError)
from django_evolution.signature import AppSignature
from django_evolution.support import supports_migrations
from django_evolution.tests.base_test_case import (MigrationsTestsMixin,
                                                   TestCase)
from django_evolution.tests.decorators import (
    requires_migrations,
    requires_migration_history_checks)
from django_evolution.tests.models import BaseTestModel
from django_evolution.tests.utils import register_models
from django_evolution.utils.migrations import (MigrationExecutor,
                                               MigrationList,
                                               MigrationLoader,
                                               apply_migrations,
                                               create_pre_migrate_state,
                                               filter_migration_targets,
                                               finalize_migrations,
                                               has_migrations_module,
                                               is_migration_initial,
                                               record_applied_migrations,
                                               unrecord_applied_migrations)


class MigrationTestModel(BaseTestModel):
    field1 = models.IntegerField()
    field2 = models.CharField(max_length=10)
    field3 = models.BooleanField()


if migrations:
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
else:
    InitialMigration = None
    AddFieldMigration = None


class MigrationListTests(TestCase):
    """Unit tests for django_evolution.utils.migrations.MigrationList."""

    def test_from_app_sig(self):
        """Testing MigrationList.from_app_sig"""
        app_sig = AppSignature(
            app_id='tests',
            applied_migrations=['0001_initial', '0002_stuff'])

        migration_list = MigrationList.from_app_sig(app_sig)
        self.assertTrue(migration_list.has_migration_info(app_label='tests',
                                                          name='0001_initial'))
        self.assertTrue(migration_list.has_migration_info(app_label='tests',
                                                          name='0002_stuff'))

    @requires_migrations
    def test_from_database(self):
        """Testing MigrationList.from_database"""
        connection = connections[DEFAULT_DB_ALIAS]

        applied_migrations = MigrationList()
        applied_migrations.add_migration_info(app_label='tests',
                                              name='0001_initial')
        applied_migrations.add_migration_info(app_label='tests',
                                              name='0002_stuff')
        record_applied_migrations(connection=connection,
                                  migrations=applied_migrations)

        migration_list = MigrationList.from_database(connection)
        self.assertTrue(migration_list.has_migration_info(app_label='tests',
                                                          name='0001_initial'))
        self.assertTrue(migration_list.has_migration_info(app_label='tests',
                                                          name='0002_stuff'))

    def test_from_names(self):
        """Testing MigrationList.from_names"""
        migration_list = MigrationList.from_names(
            app_label='tests',
            migration_names=['0001_initial', '0002_stuff'])
        self.assertTrue(migration_list.has_migration_info(app_label='tests',
                                                          name='0001_initial'))
        self.assertTrue(migration_list.has_migration_info(app_label='tests',
                                                          name='0002_stuff'))

    def test_has_migration_info(self):
        """Testing MigrationList.has_migration_info"""
        migration_list = MigrationList()
        migration_list.add_migration_info(app_label='tests',
                                          name='0001_initial')

        self.assertTrue(migration_list.has_migration_info(
            app_label='tests',
            name='0001_initial'))
        self.assertFalse(migration_list.has_migration_info(
            app_label='tests',
            name='0002_initial'))
        self.assertFalse(migration_list.has_migration_info(
            app_label='foo',
            name='0001_initial'))

    def test_add_migration_targets(self):
        """Testing MigrationList.add_migration_targets"""
        migration_list = MigrationList()
        migration_list.add_migration_targets([
            ('tests', '0001_initial'),
            ('tests', '0002_stuff'),
        ])

        self.assertEqual(
            migration_list._by_id,
            {
                ('tests', '0001_initial'): {
                    'app_label': 'tests',
                    'name': '0001_initial',
                    'migration': None,
                    'recorded_migration': None,
                },
                ('tests', '0002_stuff'): {
                    'app_label': 'tests',
                    'name': '0002_stuff',
                    'migration': None,
                    'recorded_migration': None,
                },
            })
        self.assertEqual(
            migration_list._by_app_label,
            {
                'tests': [
                    {
                        'app_label': 'tests',
                        'name': '0001_initial',
                        'migration': None,
                        'recorded_migration': None,
                    },
                    {
                        'app_label': 'tests',
                        'name': '0002_stuff',
                        'migration': None,
                        'recorded_migration': None,
                    },
                ],
            })

    @requires_migrations
    def test_add_migration(self):
        """Testing MigrationList.add_migration"""
        migration1 = InitialMigration('0001_initial', 'tests')
        migration2 = AddFieldMigration('0002_add_field', 'tests')

        migration_list = MigrationList()
        migration_list.add_migration(migration1)
        migration_list.add_migration(migration2)

        self.assertEqual(
            migration_list._by_id,
            {
                ('tests', '0001_initial'): {
                    'app_label': 'tests',
                    'name': '0001_initial',
                    'migration': migration1,
                    'recorded_migration': None,
                },
                ('tests', '0002_add_field'): {
                    'app_label': 'tests',
                    'name': '0002_add_field',
                    'migration': migration2,
                    'recorded_migration': None,
                },
            })
        self.assertEqual(
            migration_list._by_app_label,
            {
                'tests': [
                    {
                        'app_label': 'tests',
                        'name': '0001_initial',
                        'migration': migration1,
                        'recorded_migration': None,
                    },
                    {
                        'app_label': 'tests',
                        'name': '0002_add_field',
                        'migration': migration2,
                        'recorded_migration': None,
                    },
                ],
            })

    @requires_migrations
    def test_add_recorded_migration(self):
        """Testing MigrationList.add_recorded_migration"""
        recorded_migration1 = MigrationRecorder.Migration(
            app='tests',
            name='0001_initial',
            applied=True)
        recorded_migration2 = MigrationRecorder.Migration(
            app='tests',
            name='0002_add_field',
            applied=True)

        migration_list = MigrationList()
        migration_list.add_recorded_migration(recorded_migration1)
        migration_list.add_recorded_migration(recorded_migration2)

        self.assertEqual(
            migration_list._by_id,
            {
                ('tests', '0001_initial'): {
                    'app_label': 'tests',
                    'name': '0001_initial',
                    'migration': None,
                    'recorded_migration': recorded_migration1,
                },
                ('tests', '0002_add_field'): {
                    'app_label': 'tests',
                    'name': '0002_add_field',
                    'migration': None,
                    'recorded_migration': recorded_migration2,
                },
            })
        self.assertEqual(
            migration_list._by_app_label,
            {
                'tests': [
                    {
                        'app_label': 'tests',
                        'name': '0001_initial',
                        'migration': None,
                        'recorded_migration': recorded_migration1,
                    },
                    {
                        'app_label': 'tests',
                        'name': '0002_add_field',
                        'migration': None,
                        'recorded_migration': recorded_migration2,
                    },
                ],
            })

    def test_add_migration_info(self):
        """Testing MigrationList.add_migration_info"""
        if supports_migrations:
            migration1 = InitialMigration('0001_initial', 'tests')
            migration2 = AddFieldMigration('0002_add_field', 'tests')
            recorded_migration1 = MigrationRecorder.Migration(
                app='tests',
                name='0001_initial',
                applied=True)
            recorded_migration2 = MigrationRecorder.Migration(
                app='tests',
                name='0002_add_field',
                applied=True)
        else:
            migration1 = None
            migration2 = None
            recorded_migration1 = None
            recorded_migration2 = None

        migration_list = MigrationList()
        migration_list.add_migration_info(
            app_label='tests',
            name='0001_initial',
            migration=migration1,
            recorded_migration=recorded_migration1)
        migration_list.add_migration_info(
            app_label='tests',
            name='0002_add_field',
            migration=migration2,
            recorded_migration=recorded_migration2)

        self.assertEqual(
            migration_list._by_id,
            {
                ('tests', '0001_initial'): {
                    'app_label': 'tests',
                    'name': '0001_initial',
                    'migration': migration1,
                    'recorded_migration': recorded_migration1,
                },
                ('tests', '0002_add_field'): {
                    'app_label': 'tests',
                    'name': '0002_add_field',
                    'migration': migration2,
                    'recorded_migration': recorded_migration2,
                },
            })
        self.assertEqual(
            migration_list._by_app_label,
            {
                'tests': [
                    {
                        'app_label': 'tests',
                        'name': '0001_initial',
                        'migration': migration1,
                        'recorded_migration': recorded_migration1,
                    },
                    {
                        'app_label': 'tests',
                        'name': '0002_add_field',
                        'migration': migration2,
                        'recorded_migration': recorded_migration2,
                    },
                ],
            })

    def test_update(self):
        """Testing MigrationList.update"""
        if supports_migrations:
            migration1 = InitialMigration('0001_initial', 'tests')
            migration2 = AddFieldMigration('0002_add_field', 'tests')
            recorded_migration1 = MigrationRecorder.Migration(
                app='tests',
                name='0001_initial',
                applied=True)
            recorded_migration2 = MigrationRecorder.Migration(
                app='tests',
                name='0002_add_field',
                applied=True)
        else:
            migration1 = None
            migration2 = None
            recorded_migration1 = None
            recorded_migration2 = None

        migration_list1 = MigrationList()
        migration_list1.add_migration_info(
            app_label='tests',
            name='0001_initial',
            migration=migration1,
            recorded_migration=recorded_migration1)
        migration_list1.add_migration_info(
            app_label='tests',
            name='0002_add_field',
            migration=None,
            recorded_migration=None)

        migration_list2 = MigrationList()
        migration_list2.add_migration_info(
            app_label='tests',
            name='0002_add_field',
            migration=migration2,
            recorded_migration=recorded_migration2)
        migration_list2.add_migration_info(
            app_label='foo',
            name='0001_initial')

        migration_list1.update(migration_list2)

        self.assertEqual(
            migration_list1._by_id,
            {
                ('tests', '0001_initial'): {
                    'app_label': 'tests',
                    'name': '0001_initial',
                    'migration': migration1,
                    'recorded_migration': recorded_migration1,
                },
                ('tests', '0002_add_field'): {
                    'app_label': 'tests',
                    'name': '0002_add_field',
                    'migration': migration2,
                    'recorded_migration': recorded_migration2,
                },
                ('foo', '0001_initial'): {
                    'app_label': 'foo',
                    'name': '0001_initial',
                    'migration': None,
                    'recorded_migration': None,
                },
            })
        self.assertEqual(
            migration_list1._by_app_label,
            {
                'foo': [
                    {
                        'app_label': 'foo',
                        'name': '0001_initial',
                        'migration': None,
                        'recorded_migration': None,
                    },
                ],
                'tests': [
                    {
                        'app_label': 'tests',
                        'name': '0001_initial',
                        'migration': migration1,
                        'recorded_migration': recorded_migration1,
                    },
                    {
                        'app_label': 'tests',
                        'name': '0002_add_field',
                        'migration': migration2,
                        'recorded_migration': recorded_migration2,
                    },
                ],
            })

    def test_to_targets(self):
        """Testing MigrationList.to_targets"""
        migration_list = MigrationList()
        migration_list.add_migration_info(app_label='tests',
                                          name='0001_initial')
        migration_list.add_migration_info(app_label='foo',
                                          name='0002_bar')

        self.assertEqual(
            migration_list.to_targets(),
            {('tests', '0001_initial'), ('foo', '0002_bar')})

    def test_get_app_labels(self):
        """Testing MigrationList.get_app_labels"""
        migration_list = MigrationList()
        migration_list.add_migration_info(app_label='foo',
                                          name='0002_bar')
        migration_list.add_migration_info(app_label='tests',
                                          name='0001_initial')
        migration_list.add_migration_info(app_label='baz',
                                          name='0002_stuff')

        self.assertEqual(migration_list.get_app_labels(),
                         ['baz', 'foo', 'tests'])

    def test_clone(self):
        """Testing MigrationList.clone"""
        migration_list = MigrationList()
        migration_list.add_migration_info(app_label='tests',
                                          name='0001_initial')
        migration_list.add_migration_info(app_label='foo',
                                          name='0002_bar')

        cloned = migration_list.clone()
        self.assertIsNot(migration_list._by_id, cloned._by_id)
        self.assertIsNot(migration_list._by_app_label, cloned._by_app_label)
        self.assertEqual(migration_list._by_id, cloned._by_id)
        self.assertEqual(migration_list._by_app_label, cloned._by_app_label)

        # Change something in the original and make sure the clone isn't
        # affected.
        migration_list._by_id[('tests', '0001_initial')]['name'] = 'changed'
        self.assertNotEqual(migration_list._by_id, cloned._by_id)
        self.assertNotEqual(migration_list._by_app_label, cloned._by_app_label)

    def test_bool(self):
        """Testing MigrationList.__bool__"""
        migration_list = MigrationList()
        self.assertFalse(migration_list)

        migration_list.add_migration_info(app_label='tests',
                                          name='0001_initial')
        self.assertTrue(migration_list)

    def test_len(self):
        """Testing MigrationList.__len__"""
        migration_list = MigrationList()
        self.assertEqual(len(migration_list), 0)

        migration_list.add_migration_info(app_label='tests',
                                          name='0001_initial')
        self.assertEqual(len(migration_list), 1)

        migration_list.add_migration_info(app_label='tests',
                                          name='0002_stuff')
        self.assertEqual(len(migration_list), 2)

    def test_eq(self):
        """Testing MigrationList.__eq__"""
        migration_list1 = MigrationList()
        migration_list2 = MigrationList()

        self.assertEqual(migration_list1, migration_list2)
        self.assertNotEqual(migration_list1, None)
        self.assertNotEqual(migration_list1, ['abc'])
        self.assertNotEqual(migration_list1, 123)

        migration_list1.add_migration_info(app_label='tests',
                                           name='0001_initial')
        self.assertNotEqual(migration_list1, migration_list2)

        migration_list2.add_migration_info(app_label='tests',
                                           name='0001_initial')
        self.assertEqual(migration_list1, migration_list2)

        migration_list2.add_migration_info(app_label='foo',
                                           name='0001_bar')
        self.assertNotEqual(migration_list1, migration_list2)

    def test_iter(self):
        """Testing MigrationList.__iter__"""
        migration_list = MigrationList()
        migration_list.add_migration_info(app_label='tests',
                                          name='0001_initial')
        migration_list.add_migration_info(app_label='tests',
                                          name='0002_stuff')

        self.assertEqual(
            list(migration_list),
            [
                {
                    'app_label': 'tests',
                    'name': '0001_initial',
                    'migration': None,
                    'recorded_migration': None,
                },
                {
                    'app_label': 'tests',
                    'name': '0002_stuff',
                    'migration': None,
                    'recorded_migration': None,
                },
            ])

    def test_add(self):
        """Testing MigrationList.__add__"""
        migration_list1 = MigrationList()
        migration_list1.add_migration_info(app_label='tests',
                                           name='0001_initial')
        migration_list1.add_migration_info(app_label='tests',
                                           name='0002_stuff')

        migration_list2 = MigrationList()
        migration_list2.add_migration_info(app_label='tests',
                                           name='0001_initial')
        migration_list2.add_migration_info(app_label='foo',
                                           name='0002_bar')

        new_migration_list = migration_list1 + migration_list2

        self.assertEqual(
            new_migration_list._by_id,
            {
                ('tests', '0001_initial'): {
                    'app_label': 'tests',
                    'name': '0001_initial',
                    'migration': None,
                    'recorded_migration': None,
                },
                ('tests', '0002_stuff'): {
                    'app_label': 'tests',
                    'name': '0002_stuff',
                    'migration': None,
                    'recorded_migration': None,
                },
                ('foo', '0002_bar'): {
                    'app_label': 'foo',
                    'name': '0002_bar',
                    'migration': None,
                    'recorded_migration': None,
                },
            })
        self.assertEqual(
            new_migration_list._by_app_label,
            {
                'foo': [
                    {
                        'app_label': 'foo',
                        'name': '0002_bar',
                        'migration': None,
                        'recorded_migration': None,
                    },
                ],
                'tests': [
                    {
                        'app_label': 'tests',
                        'name': '0001_initial',
                        'migration': None,
                        'recorded_migration': None,
                    },
                    {
                        'app_label': 'tests',
                        'name': '0002_stuff',
                        'migration': None,
                        'recorded_migration': None,
                    },
                ],
            })

        # Make sure there's no cross-contamination.
        self.assertNotEqual(new_migration_list._by_id, migration_list1._by_id)
        self.assertNotEqual(new_migration_list._by_id, migration_list2._by_id)
        self.assertNotEqual(migration_list1._by_id, migration_list2._by_id)

    def test_sub(self):
        """Testing MigrationList.__sub__"""
        migration_list1 = MigrationList()
        migration_list1.add_migration_info(app_label='tests',
                                           name='0001_initial')
        migration_list1.add_migration_info(app_label='tests',
                                           name='0002_stuff')

        migration_list2 = MigrationList()
        migration_list2.add_migration_info(app_label='tests',
                                           name='0001_initial')
        migration_list2.add_migration_info(app_label='foo',
                                           name='0002_bar')

        new_migration_list = migration_list1 - migration_list2

        self.assertEqual(
            new_migration_list._by_id,
            {
                ('tests', '0002_stuff'): {
                    'app_label': 'tests',
                    'name': '0002_stuff',
                    'migration': None,
                    'recorded_migration': None,
                },
            })
        self.assertEqual(
            new_migration_list._by_app_label,
            {
                'tests': [
                    {
                        'app_label': 'tests',
                        'name': '0002_stuff',
                        'migration': None,
                        'recorded_migration': None,
                    },
                ],
            })

        # Make sure there's no cross-contamination.
        self.assertNotEqual(new_migration_list._by_id, migration_list1._by_id)
        self.assertNotEqual(new_migration_list._by_id, migration_list2._by_id)
        self.assertNotEqual(migration_list1._by_id, migration_list2._by_id)


class MigrationLoadTests(MigrationsTestsMixin, TestCase):
    """Unit tests for django_evolution.utils.migrations.MigrationLoader."""

    @requires_migrations
    def test_build_graph(self):
        """Testing MigrationLoader.build_graph"""
        loader = MigrationLoader(connection=connections[DEFAULT_DB_ALIAS])
        graph = loader.graph
        migration = loader.get_migration('auth', '0001_initial')

        loader.build_graph()
        self.assertIsNot(loader.graph, graph)
        self.assertIsNot(loader.get_migration('auth', '0001_initial'),
                         migration)

    @requires_migrations
    def test_build_graph_with_reload_migrations_false(self):
        """Testing MigrationLoader.build_graph with reload_migrations=False"""
        loader = MigrationLoader(connection=connections[DEFAULT_DB_ALIAS])
        graph = loader.graph
        migration = loader.get_migration('auth', '0001_initial')

        loader.build_graph(reload_migrations=False)
        self.assertIsNot(loader.graph, graph)
        self.assertIs(loader.get_migration('auth', '0001_initial'),
                      migration)


class MigrationExecutorTests(MigrationsTestsMixin, TestCase):
    """Unit tests for django_evolution.utils.migrations.MigrationExecutor."""

    @requires_migration_history_checks
    def test_run_checks_with_bad_history(self):
        """Testing MigrationExecutor.run_checks with bad history"""
        connection = connections[DEFAULT_DB_ALIAS]

        applied_migrations = MigrationList()
        applied_migrations.add_migration_info(app_label='tests',
                                              name='0002_add_field')
        record_applied_migrations(connection=connection,
                                  migrations=applied_migrations)

        custom_migrations = MigrationList()
        custom_migrations.add_migration(
            InitialMigration('0001_initial', 'tests'))
        custom_migrations.add_migration(
            AddFieldMigration('0002_add_field', 'tests'))

        executor = MigrationExecutor(connection=connection,
                                     custom_migrations=custom_migrations)

        with self.assertRaises(MigrationHistoryError):
            executor.run_checks()

    @requires_migrations
    def test_run_checks_with_conflicts(self):
        """Testing MigrationExecutor.run_checks with conflicts"""
        connection = connections[DEFAULT_DB_ALIAS]

        custom_migrations = MigrationList()
        custom_migrations.add_migration(
            InitialMigration('0001_initial', 'tests'))
        custom_migrations.add_migration(
            InitialMigration('0002_also_initial', 'tests'))

        executor = MigrationExecutor(connection=connection,
                                     custom_migrations=custom_migrations)

        message = (
            "Conflicting migrations detected; multiple leaf nodes in the "
            "migration graph: (0001_initial, 0002_also_initial in tests).\n"
            "To fix them run 'python manage.py makemigrations --merge'"
        )

        with self.assertRaisesMessage(MigrationConflictsError, message):
            executor.run_checks()


class MigrationUtilsTests(MigrationsTestsMixin, TestCase):
    """Unit tests for django_evolution.utils.migrations."""

    @requires_migrations
    def test_has_migrations_module(self):
        """Testing has_migrations_module"""
        self.assertFalse(has_migrations_module(get_app('django_evolution')))
        self.assertTrue(has_migrations_module(get_app('auth')))

    @requires_migrations
    def test_record_applied_migrations(self):
        """Testing record_applied_migrations"""
        connection = connections[DEFAULT_DB_ALIAS]

        # Ideally we'd do an assertNumQueries(2), but MigrationRecorder doesn't
        # cache state and performs repeated queries for the same list of
        # installed table names, followed by new transactions. That might
        # differ depending on the type of database being used.
        migrations = MigrationList()
        migrations.add_migration_info(app_label='tests',
                                      name='0001_initial')
        migrations.add_migration_info(app_label='tests',
                                      name='0002_stuff')

        record_applied_migrations(connection=connection,
                                  migrations=migrations)

        recorder = MigrationRecorder(connection)
        applied_migrations = recorder.applied_migrations()

        self.assertIn(('tests', '0001_initial'), applied_migrations)
        self.assertIn(('tests', '0002_stuff'), applied_migrations)

    @requires_migrations
    def test_unrecord_applied_migrations(self):
        """Testing unrecord_applied_migrations"""
        connection = connections[DEFAULT_DB_ALIAS]

        migrations = MigrationList()
        migrations.add_migration_info(app_label='tests',
                                      name='0001_initial')
        migrations.add_migration_info(app_label='tests',
                                      name='0002_stuff')

        record_applied_migrations(connection=connection,
                                  migrations=migrations)

        unrecord_applied_migrations(connection=connection,
                                    app_label='tests',
                                    migration_names=['0001_initial',
                                                     '0002_stuff'])

        recorder = MigrationRecorder(connection)
        applied_migrations = recorder.applied_migrations()

        self.assertNotIn(('tests', '0001_initial'), applied_migrations)
        self.assertNotIn(('tests', '0002_stuff'), applied_migrations)

    def test_filter_migration_targets_with_app_labels(self):
        """Testing filter_migration_targets with app_labels=..."""
        targets = [
            ('app1', '0001_initial'),
            ('app1', '0002_stuff'),
            ('app2', '0001_initial'),
            ('app3', '0001_initial'),
            ('app4', '0001_initial'),
            ('app4', '0002_more_stuff'),
        ]

        self.assertEqual(
            filter_migration_targets(targets=targets,
                                     app_labels=['app1', 'app4']),
            [
                ('app1', '0001_initial'),
                ('app1', '0002_stuff'),
                ('app4', '0001_initial'),
                ('app4', '0002_more_stuff'),
            ])

    def test_filter_migration_targets_with_exclude(self):
        """Testing filter_migration_targets with exclude=..."""
        targets = [
            ('app1', '0001_initial'),
            ('app1', '0002_stuff'),
            ('app2', '0001_initial'),
            ('app3', '0001_initial'),
            ('app4', '0001_initial'),
            ('app4', '0002_more_stuff'),
        ]

        self.assertEqual(
            filter_migration_targets(
                targets=targets,
                exclude=[
                    ('app3', '0001_initial'),
                    ('app1', '0002_stuff'),
                ]
            ),
            [
                ('app1', '0001_initial'),
                ('app2', '0001_initial'),
                ('app4', '0001_initial'),
                ('app4', '0002_more_stuff'),
            ])

    @requires_migrations
    def test_is_migration_initial_with_false(self):
        """Testing is_migration_initial with Migration.initial = False"""
        class MyMigration(migrations.Migration):
            initial = False

        self.assertFalse(is_migration_initial(MyMigration('0001_initial',
                                                          'tests')))

    @requires_migrations
    def test_is_migration_initial_with_true(self):
        """Testing is_migration_initial with Migration.initial = True"""
        class MyMigration(migrations.Migration):
            initial = True

        self.assertTrue(is_migration_initial(MyMigration('0001_initial',
                                                         'tests')))

    @requires_migrations
    def test_is_migration_initial_with_no_parent_dep_in_app(self):
        """Testing is_migration_initial with no parent dependency in same app
        """
        class MyMigration(migrations.Migration):
            dependencies = [
                ('other_app', 'some_dep'),
            ]

        self.assertTrue(is_migration_initial(MyMigration('0001_initial',
                                                         'tests')))

    @requires_migrations
    def test_is_migration_initial_with_parent_dep_in_app(self):
        """Testing is_migration_initial with parent dependency in same app"""
        class MyMigration(migrations.Migration):
            dependencies = [
                ('tests', 'some_dep'),
            ]

        self.assertFalse(is_migration_initial(MyMigration('0001_initial',
                                                          'tests')))

    @requires_migrations
    def test_apply_migrations(self):
        """Testing apply_migrations"""
        database_state = DatabaseState(db_name=DEFAULT_DB_ALIAS)
        register_models(database_state=database_state,
                        models=[('MigrationTestModel', MigrationTestModel)])

        app_migrations = [
            InitialMigration('0001_initial', 'tests'),
            AddFieldMigration('0002_add_field', 'tests'),
        ]

        targets = [
            ('tests', '0001_initial'),
            ('tests', '0002_add_field'),
        ]

        custom_migrations = MigrationList()
        custom_migrations.add_migration(app_migrations[0])
        custom_migrations.add_migration(app_migrations[1])

        connection = connections[DEFAULT_DB_ALIAS]
        executor = MigrationExecutor(connection,
                                     custom_migrations=custom_migrations)

        migrate_state = apply_migrations(
            executor=executor,
            targets=targets,
            plan=[
                (app_migrations[0], False),
                (app_migrations[1], False),
            ],
            pre_migrate_state=create_pre_migrate_state(executor))
        finalize_migrations(migrate_state)

        # Make sure this is in the database now.
        MigrationTestModel.objects.create(field1=123,
                                          field2='abc',
                                          field3=True)

"""Unit tests for django_evolution.utils.migrations."""

from __future__ import unicode_literals

from unittest import SkipTest

import django
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
from django_evolution.support import supports_migrations
from django_evolution.tests.base_test_case import (MigrationsTestsMixin,
                                                   TestCase)
from django_evolution.tests.models import BaseTestModel
from django_evolution.tests.utils import register_models
from django_evolution.utils.migrations import (MigrationExecutor,
                                               apply_migrations,
                                               filter_migration_targets,
                                               get_applied_migrations_by_app,
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


class MigrationExecutorTests(MigrationsTestsMixin, TestCase):
    """Unit tests for django_evolution.utils.migrations.MigrationExecutor."""

    def test_run_checks_with_bad_history(self):
        """Testing MigrationExecutor.run_checks with bad history"""
        if django.VERSION[:2] < (1, 10):
            raise SkipTest('Not supported on Django < 1.10')

        connection = connections[DEFAULT_DB_ALIAS]

        record_applied_migrations(
            connection=connection,
            migration_targets=[('tests', '0002_add_field')])

        executor = MigrationExecutor(
            connection=connection,
            custom_migrations={
                ('tests', '0001_initial'):
                    InitialMigration('0001_initial', 'tests'),
                ('tests', '0002_add_field'):
                    AddFieldMigration('0002_add_field', 'tests'),
            })

        with self.assertRaises(MigrationHistoryError):
            executor.run_checks()

    def test_run_checks_with_conflicts(self):
        """Testing MigrationExecutor.run_checks with conflicts"""
        if django.VERSION[:2] < (1, 7):
            raise SkipTest('Not supported on Django < 1.7')

        connection = connections[DEFAULT_DB_ALIAS]

        executor = MigrationExecutor(
            connection=connection,
            custom_migrations={
                ('tests', '0001_initial'):
                    InitialMigration('0001_initial', 'tests'),
                ('tests', '0002_also_initial'):
                    InitialMigration('0002_also_initial', 'tests'),
            })

        message = (
            "Conflicting migrations detected; multiple leaf nodes in the "
            "migration graph: (0001_initial, 0002_also_initial in tests).\n"
            "To fix them run 'python manage.py makemigrations --merge'"
        )

        with self.assertRaisesMessage(MigrationConflictsError, message):
            executor.run_checks()


class MigrationUtilsTests(MigrationsTestsMixin, TestCase):
    """Unit tests for django_evolution.utils.migrations."""

    def test_has_migrations_module(self):
        """Testing has_migrations_module"""
        if not supports_migrations:
            raise SkipTest('Not used on Django < 1.7')

        self.assertFalse(has_migrations_module(get_app('django_evolution')))
        self.assertTrue(has_migrations_module(get_app('auth')))

    def test_get_applied_migrations_by_app(self):
        """Testing get_applied_migrations_by_app"""
        if not supports_migrations:
            raise SkipTest('Not used on Django < 1.7')

        by_app = get_applied_migrations_by_app(connections[DEFAULT_DB_ALIAS])
        self.assertIn('auth', by_app)
        self.assertIn('0001_initial', by_app['auth'])
        self.assertIn('contenttypes', by_app)
        self.assertIn('0001_initial', by_app['contenttypes'])
        self.assertNotIn('django_evolution', by_app)

    def test_record_applied_migrations(self):
        """Testing record_applied_migrations"""
        if not supports_migrations:
            raise SkipTest('Not used on Django < 1.7')

        connection = connections[DEFAULT_DB_ALIAS]

        # Ideally we'd do an assertNumQueries(2), but MigrationRecorder doesn't
        # cache state and performs repeated queries for the same list of
        # installed table names, followed by new transactions. That might
        # differ depending on the type of database being used.
        record_applied_migrations(
            connection=connection,
            migration_targets=[
                ('tests', '0001_initial'),
                ('tests', '0002_stuff'),
            ])

        recorder = MigrationRecorder(connection)
        applied_migrations = recorder.applied_migrations()

        self.assertIn(('tests', '0001_initial'), applied_migrations)
        self.assertIn(('tests', '0002_stuff'), applied_migrations)

    def test_unrecord_applied_migrations(self):
        """Testing unrecord_applied_migrations"""
        if not supports_migrations:
            raise SkipTest('Not used on Django < 1.7')

        connection = connections[DEFAULT_DB_ALIAS]
        record_applied_migrations(
            connection=connection,
            migration_targets=[
                ('tests', '0001_initial'),
                ('tests', '0002_stuff'),
            ])

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

    def test_is_migration_initial_with_false(self):
        """Testing is_migration_initial with Migration.initial = False"""
        if not supports_migrations:
            raise SkipTest('Not used on Django < 1.7')

        class MyMigration(migrations.Migration):
            initial = False

        self.assertFalse(is_migration_initial(MyMigration('0001_initial',
                                                          'tests')))

    def test_is_migration_initial_with_true(self):
        """Testing is_migration_initial with Migration.initial = True"""
        if not supports_migrations:
            raise SkipTest('Not used on Django < 1.7')

        class MyMigration(migrations.Migration):
            initial = True

        self.assertTrue(is_migration_initial(MyMigration('0001_initial',
                                                         'tests')))

    def test_is_migration_initial_with_no_parent_dep_in_app(self):
        """Testing is_migration_initial with no parent dependency in same app
        """
        if not supports_migrations:
            raise SkipTest('Not used on Django < 1.7')

        class MyMigration(migrations.Migration):
            dependencies = [
                ('other_app', 'some_dep'),
            ]

        self.assertTrue(is_migration_initial(MyMigration('0001_initial',
                                                         'tests')))

    def test_is_migration_initial_with_parent_dep_in_app(self):
        """Testing is_migration_initial with parent dependency in same app"""
        if not supports_migrations:
            raise SkipTest('Not used on Django < 1.7')

        class MyMigration(migrations.Migration):
            dependencies = [
                ('tests', 'some_dep'),
            ]

        self.assertFalse(is_migration_initial(MyMigration('0001_initial',
                                                          'tests')))

    def test_apply_migrations(self):
        """Testing apply_migrations"""
        if not supports_migrations:
            raise SkipTest('Not used on Django < 1.7')

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

        connection = connections[DEFAULT_DB_ALIAS]
        executor = MigrationExecutor(
            connection,
            custom_migrations={
                targets[0]: app_migrations[0],
                targets[1]: app_migrations[1],
            })

        apply_migrations(
            executor=executor,
            targets=targets,
            plan=[
                (app_migrations[0], False),
                (app_migrations[1], False),
            ])

        # Make sure this is in the database now.
        MigrationTestModel.objects.create(field1=123,
                                          field2='abc',
                                          field3=True)

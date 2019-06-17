"""Unit tests for django_evolution.utils.migrations."""

from __future__ import unicode_literals

from unittest import SkipTest

from django.db import connections, DEFAULT_DB_ALIAS

try:
    # Django >= 1.7
    from django.db import migrations, models
    from django.db.migrations.executor import MigrationExecutor
    from django.db.migrations.recorder import MigrationRecorder
except ImportError:
    # Django < 1.7
    MigrationExecutor = None
    MigrationRecorder = None
    migrations = None
    models = None

from django_evolution.compat.apps import get_app
from django_evolution.db.state import DatabaseState
from django_evolution.support import supports_migrations
from django_evolution.tests.base_test_case import TestCase
from django_evolution.tests.utils import register_models
from django_evolution.utils.migrations import (apply_migrations,
                                               filter_migration_targets,
                                               get_applied_migrations_by_app,
                                               has_migrations_module,
                                               record_applied_migrations)


class MigrationUtilsTests(TestCase):
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
        record_applied_migrations(connection=connection,
                                  app_label='tests',
                                  migration_names=['0001_initial',
                                                   '0002_stuff'])

        recorder = MigrationRecorder(connection)
        applied_migrations = recorder.applied_migrations()

        self.assertIn(('tests', '0001_initial'), applied_migrations)
        self.assertIn(('tests', '0002_stuff'), applied_migrations)

    def test_filter_migration_targets(self):
        """Testing filter_migration_targets"""
        targets = [
            ('app1', '0001_initial'),
            ('app1', '0002_stuff'),
            ('app2', '0001_initial'),
            ('app3', '0001_initial'),
            ('app4', '0001_initial'),
            ('app4', '0002_more_stuff'),
        ]

        self.assertEqual(
            filter_migration_targets(targets, ['app1', 'app4']),
            [
                ('app1', '0001_initial'),
                ('app1', '0002_stuff'),
                ('app4', '0001_initial'),
                ('app4', '0002_more_stuff'),
            ])

    def test_apply_migrations(self):
        """Testing apply_migrations"""
        if not supports_migrations:
            raise SkipTest('Not used on Django < 1.7')

        class MigrationTestModel(models.Model):
            field1 = models.IntegerField()
            field2 = models.CharField(max_length=10)

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

        database_state = DatabaseState(db_name=DEFAULT_DB_ALIAS)
        register_models(database_state=database_state,
                        models=[('MigrationTestModel', MigrationTestModel)])

        migration = InitialMigration('0001_initial', 'tests')
        target = ('tests', '0001_initial')

        connection = connections[DEFAULT_DB_ALIAS]
        executor = MigrationExecutor(connection)
        executor.loader.graph.add_node(target, migration)

        apply_migrations(
            executor=executor,
            targets=[target],
            plan=[(migration, False)])

        # Make sure this is in the database now.
        MigrationTestModel.objects.create(field1=123,
                                          field2='abc')

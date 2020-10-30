"""Unit tests for django_evolution.utils.evolutions."""

from __future__ import unicode_literals

import os

from django.db import models

import django_evolution
from django_evolution.compat.apps import get_app
from django_evolution.consts import EvolutionsSource, UpgradeMethod
from django_evolution.models import Version
from django_evolution.mutations import AddField, ChangeField, RenameModel
from django_evolution.support import supports_migrations
from django_evolution.tests.base_test_case import (MigrationsTestsMixin,
                                                   TestCase)
from django_evolution.utils.evolutions import (get_app_pending_mutations,
                                               get_app_upgrade_info,
                                               get_applied_evolutions,
                                               get_evolution_app_dependencies,
                                               get_evolution_dependencies,
                                               get_evolution_module,
                                               get_evolution_sequence,
                                               get_evolutions_module,
                                               get_evolutions_module_name,
                                               get_evolutions_path,
                                               get_evolutions_source)


class GetAppPendingMutationsTests(TestCase):
    """Unit tests for get_app_pending_mutations."""

    def test_with_unregistered_app_sig(self):
        """Testing get_app_pending_mutations with unregistered app signature
        """
        self.ensure_evolution_models()

        latest_version = Version.objects.current_version()
        self.assertIsNone(
            latest_version.signature.get_app_sig('evolutions_app'))

        mutations = [
            ChangeField('EvolutionsAppTestModel', 'char_field',
                        models.CharField, max_length=10),
            AddField('EvolutionsAppTestModel', 'new_field',
                     models.IntegerField, default=42,
                     null=True),
        ]

        pending_mutations = get_app_pending_mutations(
            app=get_app('evolutions_app'),
            mutations=mutations)

        self.assertEqual(pending_mutations, mutations)

    def test_excludes_unchanged_models(self):
        """Testing get_app_pending_mutations excludes mutations for unchanged
        models
        """
        self.ensure_evolution_models()

        latest_version = Version.objects.current_version()
        old_project_sig = latest_version.signature

        # Make a change in the new signature for Evolution, so it will be
        # considered for pending mutations.
        new_project_sig = old_project_sig.clone()
        model_sig = (
            new_project_sig
            .get_app_sig('django_evolution')
            .get_model_sig('Evolution')
        )
        model_sig.get_field_sig('app_label').field_attrs['max_length'] = 500

        # Only the first mutation should match.
        mutations = [
            ChangeField('Evolution', 'app_label', models.CharField,
                        max_length=500),
            AddField('Version', 'new_field', models.BooleanField,
                     default=True),
        ]

        pending_mutations = get_app_pending_mutations(
            app=get_app('django_evolution'),
            old_project_sig=old_project_sig,
            project_sig=new_project_sig,
            mutations=mutations)

        self.assertEqual(pending_mutations, [mutations[0]])

    def test_with_rename_model(self):
        """Testing get_app_pending_mutations always includes RenameModel
        mutations
        """
        self.ensure_evolution_models()

        mutations = [
            RenameModel('Version', 'ProjectVersion',
                        db_table='django_project_version'),
        ]

        pending_mutations = get_app_pending_mutations(
            app=get_app('django_evolution'),
            mutations=mutations)

        self.assertEqual(pending_mutations, mutations)


class GetEvolutionAppDependenciesTests(TestCase):
    """Unit tests for get_evolution_app_dependencies."""

    def test_with_dependencies(self):
        """Testing get_evolution_app_dependencies with dependencies"""
        self.assertEqual(
            get_evolution_app_dependencies(get_app('app_deps_app')),
            {
                'after_evolutions': {
                    'evolutions_app',
                    ('evolutions_app', 'first_evolution'),
                },
                'after_migrations': {
                    ('migrations_app', '0001_initial'),
                },
                'before_evolutions': {
                    'evolutions_app2',
                    ('evolutions_app2', 'second_evolution'),
                },
                'before_migrations': {
                    ('migrations_app2', '0002_add_field'),
                },
            })

    def test_without_dependencies(self):
        """Testing get_evolution_app_dependencies without dependencies"""
        self.assertEqual(
            get_evolution_app_dependencies(get_app('evolution_deps_app')),
            {
                'after_evolutions': set(),
                'after_migrations': set(),
                'before_evolutions': set(),
                'before_migrations': set(),
            })

    def test_with_invalid_app(self):
        """Testing get_evolution_app_dependencies with non-evolution app"""
        self.assertIsNone(
            get_evolution_app_dependencies(get_app('migrations_app')))


class GetEvolutionDependenciesTests(TestCase):
    """Unit tests for get_evolution_dependencies."""

    def test_with_dependencies(self):
        """Testing get_evolution_dependencies with dependencies"""
        self.assertEqual(
            get_evolution_dependencies(get_app('evolution_deps_app'),
                                       'test_evolution'),
            {
                'after_evolutions': {
                    'evolutions_app',
                    ('evolutions_app', 'first_evolution'),
                },
                'after_migrations': {
                    ('migrations_app', '0001_initial'),
                },
                'before_evolutions': {
                    'evolutions_app2',
                    ('evolutions_app2', 'second_evolution'),
                },
                'before_migrations': {
                    ('migrations_app2', '0002_add_field'),
                },
            })

    def test_without_dependencies(self):
        """Testing get_evolution_dependencies without dependencies"""
        self.assertEqual(
            get_evolution_dependencies(get_app('app_deps_app'),
                                       'test_evolution'),
            {
                'after_evolutions': set(),
                'after_migrations': set(),
                'before_evolutions': set(),
                'before_migrations': set(),
            })

    def test_with_move_to_django_migrations(self):
        """Testing get_evolution_dependencies with MoveToDjangoMigrations
        mutation
        """
        self.assertEqual(
            get_evolution_dependencies(get_app('admin'),
                                       'admin_move_to_migrations'),
            {
                'after_evolutions': set(),
                'after_migrations': {
                    ('admin', '0001_initial'),
                },
                'before_evolutions': set(),
                'before_migrations': set(),
            })

    def test_with_invalid_app(self):
        """Testing get_evolution_dependencies with non-evolution app"""
        self.assertIsNone(
            get_evolution_dependencies(app=get_app('migrations_app'),
                                       evolution_label='invalid_evolution'))

    def test_with_invalid_evolution(self):
        """Testing get_evolution_dependencies with invalid evolution name"""
        self.assertIsNone(
            get_evolution_dependencies(app=get_app('django_evolution'),
                                       evolution_label='invalid_evolution'))


class GetEvolutionsSequenceTests(TestCase):
    """Unit tests for get_evolution_sequence."""

    def test_with_app(self):
        """Testing get_evolution_sequence with app-provided evolutions"""
        self.assertEqual(get_evolution_sequence(get_app('evolutions_app')),
                         ['first_evolution', 'second_evolution'])

    def test_with_builtin(self):
        """Testing get_evolution_sequence with built-in evolutions"""
        self.assertEqual(
            get_evolution_sequence(get_app('contenttypes')),
            [
                'contenttypes_unique_together_baseline',
                'contenttypes_move_to_migrations',
            ])

    def test_with_project(self):
        """Testing get_evolution_sequence with project-provided evolutions"""
        custom_evolutions = {
            'django_evolution.tests.migrations_app':
                'django_evolution.tests.evolutions_app.evolutions',
        }

        with self.settings(CUSTOM_EVOLUTIONS=custom_evolutions):
            self.assertEqual(get_evolution_sequence(get_app('migrations_app')),
                             ['first_evolution', 'second_evolution'])

    def test_with_not_found(self):
        """Testing get_evolution_sequence with evolutions not found"""
        self.assertEqual(get_evolution_sequence(get_app('migrations_app')),
                         [])


class GetEvolutionsModuleNameTests(TestCase):
    """Unit tests for get_evolutions_module_name."""

    def test_with_app(self):
        """Testing get_evolutions_module_name with app-provided evolutions"""
        self.assertEqual(
            get_evolutions_module_name(get_app('django_evolution')),
            'django_evolution.evolutions')

    def test_with_builtin(self):
        """Testing get_evolutions_module with built-in evolutions"""
        self.assertEqual(
            get_evolutions_module_name(get_app('auth')),
            'django_evolution.builtin_evolutions')

    def test_with_project(self):
        """Testing get_evolutions_module_name with project-provided evolutions
        """
        custom_evolutions = {
            'django_evolution':
                'django_evolution.tests.evolutions_app.evolutions',
        }

        with self.settings(CUSTOM_EVOLUTIONS=custom_evolutions):
            self.assertEqual(
                get_evolutions_module_name(get_app('django_evolution')),
                'django_evolution.tests.evolutions_app.evolutions')


class GetEvolutionsModuleTests(TestCase):
    """Unit tests for get_evolutions_module."""

    def test_with_app(self):
        """Testing get_evolutions_module with app-provided evolutions"""
        from django_evolution import evolutions

        self.assertIs(get_evolutions_module(get_app('django_evolution')),
                      evolutions)

    def test_with_builtin(self):
        """Testing get_evolutions_module with built-in evolutions"""
        from django_evolution import builtin_evolutions

        self.assertIs(get_evolutions_module(get_app('auth')),
                      builtin_evolutions)

    def test_with_project(self):
        """Testing get_evolutions_module with project-provided evolutions"""
        from django_evolution.tests.evolutions_app import evolutions

        custom_evolutions = {
            'django_evolution':
                'django_evolution.tests.evolutions_app.evolutions',
        }

        with self.settings(CUSTOM_EVOLUTIONS=custom_evolutions):
            self.assertIs(get_evolutions_module(get_app('django_evolution')),
                          evolutions)

    def test_with_not_found(self):
        """Testing get_evolutions_module with evolutions not found"""
        self.assertIsNone(get_evolutions_module(get_app('migrations_app')))


class GetEvolutionModuleTests(TestCase):
    """Unit tests for get_evolution_module."""

    def test_with_app(self):
        """Testing get_evolution_module with app-provided evolutions"""
        from django_evolution.tests.evolutions_app.evolutions import \
            first_evolution

        self.assertIs(get_evolution_module(get_app('evolutions_app'),
                                           'first_evolution'),
                      first_evolution)

    def test_with_builtin(self):
        """Testing get_evolution_module with built-in evolutions"""
        from django_evolution.builtin_evolutions import auth_delete_message

        self.assertIs(get_evolution_module(get_app('auth'),
                                           'auth_delete_message'),
                      auth_delete_message)

    def test_with_project(self):
        """Testing get_evolution_module with project-provided evolutions"""
        from django_evolution.tests.evolutions_app.evolutions import \
            first_evolution

        custom_evolutions = {
            'django_evolution':
                'django_evolution.tests.evolutions_app.evolutions',
        }

        with self.settings(CUSTOM_EVOLUTIONS=custom_evolutions):
            self.assertIs(get_evolution_module(get_app('django_evolution'),
                                               'first_evolution'),
                          first_evolution)

    def test_with_not_found(self):
        """Testing get_evolution_module with evolutions not found"""
        self.assertIsNone(get_evolution_module(get_app('evolutions_app'),
                                               'xxx'))


class GetEvolutionsPathTests(TestCase):
    """Unit tests for get_evolutions_path."""

    base_dir = os.path.dirname(django_evolution.__file__)

    def test_with_app(self):
        """Testing get_evolutions_path with app-provided evolutions"""
        self.assertEqual(get_evolutions_path(get_app('django_evolution')),
                         os.path.join(self.base_dir, 'evolutions'))

    def test_with_builtin(self):
        """Testing get_evolutions_path with built-in evolutions"""
        self.assertEqual(get_evolutions_path(get_app('auth')),
                         os.path.join(self.base_dir, 'builtin_evolutions'))

    def test_with_project(self):
        """Testing get_evolutions_path with project-provided evolutions"""
        custom_evolutions = {
            'django_evolution.tests.evolutions_app':
                'django_evolution.tests.evolutions_app.evolutions',
        }

        with self.settings(CUSTOM_EVOLUTIONS=custom_evolutions):
            self.assertEqual(get_evolutions_path(get_app('evolutions_app')),
                             os.path.join(self.base_dir, 'tests',
                                          'evolutions_app', 'evolutions'))

    def test_with_not_found(self):
        """Testing get_evolutions_path with evolutions not found"""
        self.assertIsNone(get_evolutions_path(get_app('migrations_app')))


class GetEvolutionsSourceTests(TestCase):
    """Unit tests for get_evolutions_source."""

    def test_with_app(self):
        """Testing get_evolutions_source with app-provided evolutions"""
        self.assertEqual(get_evolutions_source(get_app('django_evolution')),
                         EvolutionsSource.APP)

    def test_with_builtin(self):
        """Testing get_evolutions_source with built-in evolutions"""
        self.assertEqual(get_evolutions_source(get_app('auth')),
                         EvolutionsSource.BUILTIN)

    def test_with_project(self):
        """Testing get_evolutions_source with project-provided evolutions"""
        custom_evolutions = {
            'django_evolution.tests.migrations_app':
                'django_evolution.tests.evolutions_app.evolutions',
        }

        with self.settings(CUSTOM_EVOLUTIONS=custom_evolutions):
            self.assertEqual(get_evolutions_source(get_app('migrations_app')),
                             EvolutionsSource.PROJECT)

    def test_with_not_found(self):
        """Testing get_evolutions_source with evolutions not found falls back
        to APP
        """
        self.assertEqual(get_evolutions_source(get_app('migrations_app')),
                         EvolutionsSource.APP)


class GetAppUpgradeInfoTests(MigrationsTestsMixin, TestCase):
    """Unit tests for get_app_upgrade_info."""

    maxDiff = None

    def test_with_evolutions(self):
        """Testing get_app_upgrade_info with evolutions"""
        app = get_app('evolutions_app')

        upgrade_info = get_app_upgrade_info(app)

        self.assertEqual(
            upgrade_info,
            {
                'applied_migrations': None,
                'has_evolutions': True,
                'has_migrations': False,
                'upgrade_method': UpgradeMethod.EVOLUTIONS,
            })
        self.assertEqual(
            get_app_upgrade_info(app, simulate_applied=True),
            upgrade_info)

    def test_with_migrations(self):
        """Testing get_app_upgrade_info with migrations only"""
        app = get_app('migrations_app')

        upgrade_info = get_app_upgrade_info(app)

        self.assertEqual(
            upgrade_info,
            {
                'applied_migrations': None,
                'has_evolutions': False,
                'has_migrations': True,
                'upgrade_method': UpgradeMethod.MIGRATIONS,
            })
        self.assertEqual(
            get_app_upgrade_info(app, simulate_applied=True),
            upgrade_info)

    def test_with_unapplied_move_to_migrations(self):
        """Testing get_app_upgrade_info with unapplied MoveToDjangoMigrations
        """
        app = get_app('auth')

        self.assertNotIn('auth_move_to_migrations',
                         get_applied_evolutions(app))

        # Check without the evolutions applied.
        upgrade_info = get_app_upgrade_info(app)

        if supports_migrations:
            self.assertTrue(
                upgrade_info['applied_migrations'].has_migration_info(
                    app_label='auth',
                    name='0001_initial'))
        else:
            self.assertIsNone(upgrade_info['applied_migrations'])

        self.assertTrue(upgrade_info['has_evolutions'])
        self.assertEqual(upgrade_info['has_migrations'],
                         supports_migrations)
        self.assertEqual(upgrade_info['upgrade_method'],
                         UpgradeMethod.EVOLUTIONS)

        # Check with the evolutions applied.
        upgrade_info = get_app_upgrade_info(app, simulate_applied=True)

        self.assertTrue(upgrade_info['applied_migrations'].has_migration_info(
            app_label='auth',
            name='0001_initial'))
        self.assertTrue(upgrade_info['has_evolutions'])
        self.assertEqual(upgrade_info['has_migrations'],
                         supports_migrations)
        self.assertEqual(upgrade_info['upgrade_method'],
                         UpgradeMethod.MIGRATIONS)

    def test_with_applied_move_to_migrations(self):
        """Testing get_app_upgrade_info with applied MoveToDjangoMigrations
        """
        app = get_app('auth')

        self.ensure_evolved_apps([app])
        self.assertIn('auth_move_to_migrations', get_applied_evolutions(app))

        # Check without the evolutions applied.
        upgrade_info = get_app_upgrade_info(app)

        if supports_migrations:
            self.assertTrue(upgrade_info['has_migrations'])
        else:
            self.assertFalse(upgrade_info['has_migrations'])

        self.assertTrue(upgrade_info['applied_migrations'].has_migration_info(
            app_label='auth',
            name='0001_initial'))
        self.assertTrue(upgrade_info['has_evolutions'])
        self.assertEqual(upgrade_info['upgrade_method'],
                         UpgradeMethod.MIGRATIONS)

        # Check with the evolutions applied.
        self.assertEqual(get_app_upgrade_info(app, simulate_applied=True),
                         upgrade_info)

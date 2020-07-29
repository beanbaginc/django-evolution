"""Unit tests for django_evolution.utils.evolutions."""

from __future__ import unicode_literals

import os

import django_evolution
from django_evolution.compat.apps import get_app
from django_evolution.consts import EvolutionsSource, UpgradeMethod
from django_evolution.models import Evolution
from django_evolution.support import supports_migrations
from django_evolution.tests.base_test_case import TestCase
from django_evolution.utils.evolutions import (get_app_upgrade_info,
                                               get_applied_evolutions,
                                               get_evolution_sequence,
                                               get_evolutions_module,
                                               get_evolutions_path,
                                               get_evolutions_source)


class GetEvolutionsSequenceTests(TestCase):
    """Unit tests for get_evolution_sequence."""

    def test_with_app(self):
        """Testing get_evolution_sequence with app-provided evolutions"""
        self.assertEqual(get_evolution_sequence(get_app('evolutions_app')),
                         ['first_evolution'])

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
                             ['first_evolution'])

    def test_with_not_found(self):
        """Testing get_evolution_sequence with evolutions not found"""
        self.assertEqual(get_evolution_sequence(get_app('migrations_app')),
                         [])


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
            'django_evolution.tests.evolutions_app':
                'django_evolution.tests.evolutions_app.evolutions',
        }

        with self.settings(CUSTOM_EVOLUTIONS=custom_evolutions):
            self.assertIs(get_evolutions_module(get_app('evolutions_app')),
                          evolutions)

    def test_with_not_found(self):
        """Testing get_evolutions_module with evolutions not found"""
        self.assertIsNone(get_evolutions_module(get_app('migrations_app')))


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


class GetAppUpgradeInfoTests(TestCase):
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

        Evolution.objects.filter(label='auth_move_to_migrations').delete()
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

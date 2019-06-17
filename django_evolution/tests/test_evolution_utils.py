"""Unit tests for django_evolution.utils.evolutions."""

from __future__ import unicode_literals

import os

import django_evolution
from django_evolution.compat.apps import get_app
from django_evolution.consts import EvolutionsSource, UpgradeMethod
from django_evolution.models import Evolution
from django_evolution.support import supports_migrations
from django_evolution.tests.base_test_case import TestCase
from django_evolution.utils.evolutions import (get_app_upgrade_method,
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
            'django.contrib.admin':
                'django_evolution.tests.evolutions_app.evolutions',
        }

        with self.settings(CUSTOM_EVOLUTIONS=custom_evolutions):
            self.assertEqual(get_evolution_sequence(get_app('admin')),
                             ['first_evolution'])

    def test_with_not_found(self):
        """Testing get_evolution_sequence with evolutions not found"""
        self.assertEqual(get_evolution_sequence(get_app('admin')),
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
            'django.contrib.admin':
                'django_evolution.tests.evolutions_app.evolutions',
        }

        with self.settings(CUSTOM_EVOLUTIONS=custom_evolutions):
            self.assertIs(get_evolutions_module(get_app('admin')),
                          evolutions)

    def test_with_not_found(self):
        """Testing get_evolutions_module with evolutions not found"""
        self.assertIsNone(get_evolutions_module(get_app('admin')))


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
            'django.contrib.admin':
                'django_evolution.tests.evolutions_app.evolutions',
        }

        with self.settings(CUSTOM_EVOLUTIONS=custom_evolutions):
            self.assertEqual(get_evolutions_path(get_app('admin')),
                             os.path.join(self.base_dir, 'tests',
                                          'evolutions_app', 'evolutions'))

    def test_with_not_found(self):
        """Testing get_evolutions_path with evolutions not found"""
        self.assertIsNone(get_evolutions_path(get_app('admin')))


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
            'django.contrib.admin':
                'django_evolution.tests.evolutions_app.evolutions',
        }

        with self.settings(CUSTOM_EVOLUTIONS=custom_evolutions):
            self.assertEqual(get_evolutions_source(get_app('admin')),
                             EvolutionsSource.PROJECT)

    def test_with_not_found(self):
        """Testing get_evolutions_source with evolutions not found falls back
        to APP
        """
        self.assertEqual(get_evolutions_source(get_app('admin')),
                         EvolutionsSource.APP)


class GetAppUpgradeMethodTests(TestCase):
    """Unit tests for get_app_upgrade_method."""

    def test_with_evolutions(self):
        """Testing get_app_upgrade_method with evolutions"""
        app = get_app('evolutions_app')

        self.assertEqual(get_app_upgrade_method(app),
                         UpgradeMethod.EVOLUTIONS)
        self.assertEqual(get_app_upgrade_method(app, simulate_applied=True),
                         UpgradeMethod.EVOLUTIONS)

    def test_with_migrations(self):
        """Testing get_app_upgrade_method with migrations only"""
        app = get_app('migrations_app')

        if supports_migrations:
            expected_value = UpgradeMethod.MIGRATIONS
        else:
            expected_value = None

        self.assertEqual(get_app_upgrade_method(app),
                         expected_value)
        self.assertEqual(get_app_upgrade_method(app, simulate_applied=True),
                         expected_value)

    def test_with_unapplied_move_to_migrations(self):
        """Testing get_app_upgrade_method with unapplied MoveToDjangoMigrations
        """
        app = get_app('auth')

        Evolution.objects.filter(label='auth_move_to_migrations').delete()
        self.assertNotIn('auth_move_to_migrations',
                         get_applied_evolutions(app))

        self.assertEqual(get_app_upgrade_method(app),
                         UpgradeMethod.EVOLUTIONS)
        self.assertEqual(get_app_upgrade_method(app, simulate_applied=True),
                         UpgradeMethod.MIGRATIONS)

    def test_with_applied_move_to_migrations(self):
        """Testing get_app_upgrade_method with applied MoveToDjangoMigrations
        """
        app = get_app('auth')

        self.assertIn('auth_move_to_migrations', get_applied_evolutions(app))
        self.assertEqual(get_app_upgrade_method(app),
                         UpgradeMethod.MIGRATIONS)
        self.assertEqual(get_app_upgrade_method(app, simulate_applied=True),
                         UpgradeMethod.MIGRATIONS)

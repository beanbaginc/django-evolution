"""Unit tests for django_evolution.utils.evolutions."""

from __future__ import unicode_literals

from django_evolution.compat.apps import get_app
from django_evolution.consts import UpgradeMethod
from django_evolution.models import Evolution
from django_evolution.support import supports_migrations
from django_evolution.tests.base_test_case import TestCase
from django_evolution.utils.evolutions import (get_app_upgrade_method,
                                               get_applied_evolutions)


class EvolutionUtilsTests(TestCase):
    """Unit tests for django_evolution.utils.evolutions."""

    def test_get_app_upgrade_method_with_evolutions(self):
        """Testing get_app_upgrade_method with evolutions"""
        app = get_app('evolutions_app')

        self.assertEqual(get_app_upgrade_method(app),
                         UpgradeMethod.EVOLUTIONS)
        self.assertEqual(get_app_upgrade_method(app, simulate_applied=True),
                         UpgradeMethod.EVOLUTIONS)

    def test_get_app_upgrade_method_with_migrations(self):
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

    def test_get_app_upgrade_method_with_unapplied_move_to_migrations(self):
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

    def test_get_app_upgrade_method_with_applied_move_to_migrations(self):
        """Testing get_app_upgrade_method with applied MoveToDjangoMigrations
        """
        app = get_app('auth')

        self.assertIn('auth_move_to_migrations', get_applied_evolutions(app))
        self.assertEqual(get_app_upgrade_method(app),
                         UpgradeMethod.MIGRATIONS)
        self.assertEqual(get_app_upgrade_method(app, simulate_applied=True),
                         UpgradeMethod.MIGRATIONS)

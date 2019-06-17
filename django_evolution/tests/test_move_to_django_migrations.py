"""Unit tests for the MoveToDjangoMigrations mutation."""

from __future__ import unicode_literals

from django.db import models

from django_evolution.consts import UpgradeMethod
from django_evolution.mutations import MoveToDjangoMigrations
from django_evolution.tests.base_test_case import EvolutionTestCase
from django_evolution.tests.models import BaseTestModel


class MoveToDjangoMigrationsBaseModel(BaseTestModel):
    char_field = models.CharField(max_length=20)


class MoveToDjangoMigrationsTests(EvolutionTestCase):
    """Unit tests for the MoveToDjangoMigrations mutation."""

    default_base_model = MoveToDjangoMigrationsBaseModel

    def test_simulate(self):
        """Testing MoveToDjangoMigrations"""
        end_sig = self.start_sig.clone()

        app_sig = end_sig.get_app_sig('tests')
        app_sig.upgrade_method = UpgradeMethod.MIGRATIONS

        mutation = MoveToDjangoMigrations(mark_applied=['0001_initial'])
        new_sig = self.perform_simulations([mutation], end_sig)

        new_app_sig = new_sig.get_app_sig('tests')
        self.assertEqual(new_app_sig.upgrade_method, UpgradeMethod.MIGRATIONS)
        self.assertEqual(new_app_sig.applied_migrations, set(['0001_initial']))

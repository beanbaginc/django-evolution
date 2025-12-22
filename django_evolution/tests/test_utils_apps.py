"""Unit tests for django_evolution.utils.apps.

Version Changed:
    3.0:
    Renamed from ``django_evolutions.tests.test_compat_apps``.
"""

from __future__ import annotations

import django
from django.core.exceptions import ImproperlyConfigured

from django_evolution.tests.base_test_case import TestCase
from django_evolution.utils.apps import get_app


class UtilsAppsTestCase(TestCase):
    """Unit tests for django_evolution.utils.apps."""

    def test_get_app_with_valid_and_has_model(self):
        """Testing get_apps with valid app containing models"""
        self.assertIsNotNone(get_app('django_evolution'))

    def test_get_app_with_valid_no_models_and_emptyok_true(self):
        """Testing get_apps with valid app without models and emptyOK=True"""
        self.assertIsNone(get_app('no_models_app', emptyOK=True))

    def test_get_app_with_valid_no_models_and_emptyok_false(self):
        """Testing get_apps with valid app without models and emptyOK=False"""
        message = 'App with label no_models_app is missing a models.py module.'

        with self.assertRaisesMessage(ImproperlyConfigured, message):
            get_app('no_models_app', emptyOK=False)

    def test_get_app_with_invalid_app_and_emptyok_true(self):
        """Testing get_apps with invalid app and emptyOK=True"""
        if django.VERSION[:2] >= (1, 7):
            message = "No installed app with label 'invalid_app'."
        else:
            message = 'App with label invalid_app could not be found'

        with self.assertRaisesMessage(ImproperlyConfigured, message):
            get_app('invalid_app', emptyOK=True)

    def test_get_app_with_invalid_app_and_emptyok_false(self):
        """Testing get_apps with invalid app and emptyOK=False"""
        if django.VERSION[:2] >= (1, 7):
            message = "No installed app with label 'invalid_app'."
        else:
            message = 'App with label invalid_app could not be found'

        with self.assertRaisesMessage(ImproperlyConfigured, message):
            get_app('invalid_app', emptyOK=False)

"""Unit tests for django_evolution.conf."""

from __future__ import unicode_literals

import pytest
from django.test.utils import override_settings

from django_evolution.conf import (DjangoEvolutionSettings,
                                   django_evolution_settings)
from django_evolution.deprecation import RemovedInDjangoEvolution30Warning
from django_evolution.tests.base_test_case import TestCase


class DjangoEvolutionSettingsTests(TestCase):
    """Unit tests for django_evolution.conf.DjangoEvolutionSettings."""

    def test_init_defaults(self):
        """Testing DjangoEvolutionSettings.__init__ sets defaults"""
        class DummySettingsModule:
            pass

        djevo_settings = DjangoEvolutionSettings(DummySettingsModule)
        self.assertEqual(djevo_settings.CUSTOM_EVOLUTIONS, {})
        self.assertTrue(djevo_settings.ENABLED)

    def test_init_defaults_with_settings(self):
        """Testing DjangoEvolutionSettings.__init__ with explicit settingss"""
        class DummySettingsModule:
            DJANGO_EVOLUTION = {
                'CUSTOM_EVOLUTIONS': {
                    'my_app': ['evolution1', 'evolution2'],
                },
                'ENABLED': False,
            }

        djevo_settings = DjangoEvolutionSettings(DummySettingsModule)
        self.assertEqual(djevo_settings.CUSTOM_EVOLUTIONS, {
            'my_app': ['evolution1', 'evolution2'],
        })
        self.assertFalse(djevo_settings.ENABLED)

    def test_init_defaults_with_deprecated_settings(self):
        """Testing DjangoEvolutionSettings.__init__ with explicit deprecated
        settings
        """
        class DummySettingsModule:
            CUSTOM_EVOLUTIONS = {
                'my_app': ['evolution1', 'evolution2'],
            }
            DJANGO_EVOLUTION_ENABLED = False

        with pytest.warns(RemovedInDjangoEvolution30Warning) as record:
            djevo_settings = DjangoEvolutionSettings(DummySettingsModule)

        self.assertEqual(len(record), 2)
        messages = sorted(
            _record.message.args[0]
            for _record in record
        )

        self.assertEqual(
            messages[0],
            'CUSTOM_EVOLUTIONS is deprecated and will be removed in Django '
            'Evolution 3.0. Please use settings.DJANGO_EVOLUTION['
            '"CUSTOM_EVOLUTIONS"] instead.')
        self.assertEqual(
            messages[1],
            'DJANGO_EVOLUTION_ENABLED is deprecated and will be removed in '
            'Django Evolution 3.0. Please use settings.DJANGO_EVOLUTION['
            '"ENABLED"] instead.')

        self.assertEqual(djevo_settings.CUSTOM_EVOLUTIONS, {
            'my_app': ['evolution1', 'evolution2'],
        })
        self.assertFalse(djevo_settings.ENABLED)

    def test_replace_settings(self):
        """Testing DjangoEvolutionSettings.replace_settings"""
        class DummySettingsModule:
            pass

        djevo_settings = DjangoEvolutionSettings(DummySettingsModule)
        djevo_settings.replace_settings({
            'CUSTOM_EVOLUTIONS': {
                'my_app': ['evolution1', 'evolution2'],
            },
            'ENABLED': False,
        })

        self.assertEqual(djevo_settings.CUSTOM_EVOLUTIONS, {
            'my_app': ['evolution1', 'evolution2'],
        })
        self.assertFalse(djevo_settings.ENABLED)

    def test_replace_settings_sets_defaults(self):
        """Testing DjangoEvolutionSettings.replace_settings sets defaults"""
        class DummySettingsModule:
            DJANGO_EVOLUTION = {
                'CUSTOM_EVOLUTIONS': {
                    'my_app': ['evolution1', 'evolution2'],
                },
                'ENABLED': False,
            }

        djevo_settings = DjangoEvolutionSettings(DummySettingsModule)
        djevo_settings.replace_settings({
            'ENABLED': False,
        })

        self.assertEqual(djevo_settings.CUSTOM_EVOLUTIONS, {})
        self.assertFalse(djevo_settings.ENABLED)


class OnSettingChangedTests(TestCase):
    """Unit tests for django_evolution.conf._on_setting_changed"""

    def tearDown(self):
        super(OnSettingChangedTests, self).tearDown()

        # Set back to defaults.
        django_evolution_settings.replace_settings({})

    def test_with_django_evolution(self):
        """Testing setting_changed with DJANGO_EVOLUTION updated"""
        new_settings = {
            'CUSTOM_EVOLUTIONS': {
                'my_app': ['evolution1', 'evolution2'],
            },
            'ENABLED': False,
        }

        with override_settings(DJANGO_EVOLUTION=new_settings):
            self.assertEqual(django_evolution_settings.CUSTOM_EVOLUTIONS, {
                'my_app': ['evolution1', 'evolution2'],
            })
            self.assertFalse(django_evolution_settings.ENABLED)

    def test_with_legacy_custom_evolutions(self):
        """Testing setting_changed with legacy CUSTOM_EVOLUTIONS updated"""
        with pytest.warns(RemovedInDjangoEvolution30Warning) as record:
            custom_evolutions = {
                'my_app': ['evolution1', 'evolution2'],
            }

            with override_settings(CUSTOM_EVOLUTIONS=custom_evolutions):
                self.assertEqual(
                    django_evolution_settings.CUSTOM_EVOLUTIONS,
                    {
                        'my_app': ['evolution1', 'evolution2'],
                    })
                self.assertTrue(django_evolution_settings.ENABLED)

        self.assertEqual(
            record[0].message.args[0],
            'CUSTOM_EVOLUTIONS is deprecated and will be removed in Django '
            'Evolution 3.0. Please use settings.DJANGO_EVOLUTION['
            '"CUSTOM_EVOLUTIONS"] instead.')

    def test_with_legacy_django_evolution_enabled(self):
        """Testing setting_changed with legacy DJANGO_EVOLUTION_ENABLED updated
        """
        with pytest.warns(RemovedInDjangoEvolution30Warning) as record:
            with override_settings(DJANGO_EVOLUTION_ENABLED=False):
                self.assertEqual(django_evolution_settings.CUSTOM_EVOLUTIONS,
                                 {})
                self.assertFalse(django_evolution_settings.ENABLED)

        self.assertEqual(
            record[0].message.args[0],
            'DJANGO_EVOLUTION_ENABLED is deprecated and will be removed in '
            'Django Evolution 3.0. Please use settings.DJANGO_EVOLUTION['
            '"ENABLED"] instead.')

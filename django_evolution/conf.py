"""Configuration for Django Evolution.

Version Added:
    2.2
"""

from __future__ import unicode_literals

from copy import deepcopy

from django.conf import settings
from django.dispatch import receiver

try:
    # Django >= 1.8
    from django.core.signals import setting_changed
except ImportError:
    # Django < 1.8
    from django.test.signals import setting_changed

from django_evolution.compat import six
from django_evolution.deprecation import RemovedInDjangoEvolution30Warning


class DjangoEvolutionSettings(object):
    """Settings for Django Evolution.

    This wraps the settings defined in :py:mod:`django.conf.settings`. If
    ``settings.DJANGO_EVOLUTION`` is set, then all supported keys will be
    loaded.

    Legacy settings ( ``settings.DJANGO_EVOLUTION_ENABLED`` and
    ``settings.CUSTOM_EVOLUTIONS``), if found, will be loaded, and will cause
    a deprecation warning to be emitted.

    Version Added:
        2.2

    Attributes:
        CUSTOM_EVOLUTIONS:
            A mapping of app labels to lists of custom evolution modules.

            Type:
                dict

        ENABLED:
            Whether Django Evolution is enabled.

            If enabled, the ``syncdb`` and ``migrate`` management commands will
            instead use Django Evolution. Post-syncdb/migrate operations will
            also cause Django Evolution to track state.

            If disabled, the management commands will operate no differently
            than in a normal Django installation.

            Type:
                bool
    """

    #: Default settings for all keys.
    _DEFAULTS = {
        'CUSTOM_EVOLUTIONS': {},
        'ENABLED': True,
    }

    #: All valid settings in settings.DJANGO_EVOLUTION.
    _VALID_SETTINGS = set(_DEFAULTS.keys())

    #: A mapping of all deprecated settings to modern settings.
    _DEPRECATED_SETTINGS = {
        'CUSTOM_EVOLUTIONS': 'CUSTOM_EVOLUTIONS',
        'DJANGO_EVOLUTION_ENABLED': 'ENABLED',
    }

    def __init__(self, settings_module):
        """Initialize the settings wrapper.

        Args:
            settings_module (module):
                The Django settings module to load from.
        """
        self.load_settings(settings_module)

    def load_settings(self, settings_module):
        """Set defaults and load settings.

        Args:
            settings_module (module):
                The Django settings module to load from.
        """
        # Load any custom settings.
        DJANGO_EVOLUTION = getattr(settings_module, 'DJANGO_EVOLUTION', None)

        if DJANGO_EVOLUTION is not None:
            self.replace_settings(DJANGO_EVOLUTION)
        else:
            # Set the defaults.
            self.replace_settings({})

            # Look for deprecated settings.
            for key in six.iterkeys(self._DEPRECATED_SETTINGS):
                if hasattr(settings_module, key):
                    self._set_deprecated_setting(
                        key,
                        getattr(settings_module, key))

    def replace_settings(self, new_settings):
        """Replace settings from a dictionary.

        This is expected to take the equivalent of a
        ``settings.DJANGO_EVOLUTION`` dictionary. Any valid settings found
        will be loaded. Any not found will be set back to defaults.

        Args:
            new_settings (dict):
                The new settings dictionary.
        """
        for key in self._VALID_SETTINGS:
            if key in new_settings:
                value = new_settings[key]
            else:
                value = deepcopy(self._DEFAULTS[key])

            setattr(self, key, value)

    def _set_deprecated_setting(self, key, value):
        """Set a deprecated setting.

        Args:
            key (unicode):
                The deprecated setting name.

            value (object):
                The new value.
        """
        new_key = self._DEPRECATED_SETTINGS[key]

        RemovedInDjangoEvolution30Warning.warn(
            '%s is deprecated and will be removed in Django '
            'Evolution 3.0. Please use '
            'settings.DJANGO_EVOLUTION["%s"] instead.'
            % (key, new_key))

        if value is None:
            value = deepcopy(self._DEFAULTS[new_key])

        setattr(self, new_key, value)


@receiver(setting_changed)
def _on_setting_changed(setting, value, **kwargs):
    """Handle changes to Django settings.

    This will update the settings in response to dynamic changes, such as
    from unit test runs.

    Version Added:
        2.2

    Args:
        setting (unicode):
            The name of the setting.

        value (object):
            The new value.

        **kwargs (dict, unused):
            Extra keyword arguments passed to the signal.
    """
    if setting == 'DJANGO_EVOLUTION':
        django_evolution_settings.replace_settings(value or {})
    elif setting in django_evolution_settings._DEPRECATED_SETTINGS:
        django_evolution_settings._set_deprecated_setting(setting, value)


django_evolution_settings = DjangoEvolutionSettings(settings)

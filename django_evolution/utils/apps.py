"""Utilities for working with apps."""

from __future__ import unicode_literals

from importlib import import_module

from django.conf import settings
from django.utils.module_loading import module_has_submodule

from django_evolution.compat.apps import apps


def get_app_config_for_app(app):
    """Return the app configuration for an app.

    This can only be called if running on Django 1.7 or higher.

    Args:
        app (module):
            The app's models module to return the configuration for.
            The models module is used for legacy reasons within Django
            Evolution.

    Returns:
        django.apps.AppConfig:
        The app configuration, or ``None`` if it couldn't be found.
    """
    assert apps, \
        'get_app_config_for_app() can only be called on Django >= 1.7'

    for app_config in apps.get_app_configs():
        if app_config.models_module is app:
            return app_config

    return None


def get_app_label(app):
    """Return the label of an app.

    Args:
        app (module):
            The app.

    Returns:
        str:
        The label of the app.
    """
    if apps:
        # Django >= 1.7
        return get_app_config_for_app(app).label
    else:
        # Django < 1.7
        return get_legacy_app_label(app)


def get_app_name(app):
    """Return the name of an app.

    Args:
        app (module):
            The app.

    Returns:
        str:
        The name of the app.
    """
    if apps:
        # Django >= 1.7
        app_config = get_app_config_for_app(app)

        return app_config.name
    else:
        # Django < 1.7
        return '.'.join(app.__name__.split('.')[:-1])


def get_legacy_app_label(app):
    """Return the label of an app.

    Args:
        app (module):
            The app.

    Returns:
        str:
        The label of the app.
    """
    return app.__name__.split('.')[-2]


def import_management_modules():
    """Import the management modules for all apps.

    Management modules often contain signal handlers for pre/post
    syncdb/migrate events. This will import them correctly for the current
    version of Django.

    Raises:
        ImportError:
            A management module failed to import.
    """
    if apps:
        # Django >= 1.7
        app_names_modules = [
            (app_config.name, app_config.module)
            for app_config in apps.get_app_configs()
        ]
    else:
        # Django < 1.7
        app_names_modules = [
            (app_name, import_module(app_name))
            for app_name in settings.INSTALLED_APPS
        ]

    for (app_name, app_module) in app_names_modules:
        if module_has_submodule(app_module, 'management'):
            import_module('.management', app_name)

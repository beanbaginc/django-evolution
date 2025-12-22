"""Utilities for working with apps."""

from __future__ import annotations

from importlib import import_module

from django.apps.config import AppConfig
from django.apps.registry import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import module_has_submodule

from django_evolution.compat.datastructures import OrderedDict
from django_evolution.compat.models import all_models


def get_apps():
    """Return the list of all installed apps with models.

    Version Changed:
        3.0:
        Moved from ``django.compat.apps``.

    Returns:
        list:
        A list of all the modules containing model classes.
    """
    return [
        app.models_module
        for app in apps.get_app_configs()
        if app.models_module is not None
    ]


def get_app(app_label, emptyOK=False):
    """Return the app with the given label.

    Version Changed:
        3.0:
        Moved from ``django.compat.apps``.

    Args:
        app_label (str):
            The label for the app containing the models.

        emptyOK (bool, optional):
            Impacts the return value if the app has no models in it.

    Returns:
        module:
        The app module, if available.

        If the app module is available, but the models module is not and
        ``emptyOK`` is set, this will return ``None``. Otherwise, if modules
        are not available, this will raise
        :py:exc:`~django.core.exceptions.ImproperlyConfigured`.

    Raises:
        django.core.exceptions.ImproperlyConfigured:
            The app module was not found, or it was found but a models module
            was not and ``emptyOK`` was ``False``.
    """
    try:
        models_module = apps.get_app_config(app_label).models_module
    except LookupError as e:
        # Convert this to an ImproperlyConfigured.
        raise ImproperlyConfigured(*e.args)

    if models_module is None and not emptyOK:
        # This is the exact error that Django 1.6 provided.
        raise ImproperlyConfigured(
            'App with label %s is missing a models.py module.'
            % app_label)

    return models_module


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
    return get_app_config_for_app(app).label


def get_app_name(app):
    """Return the name of an app.

    Args:
        app (module):
            The app.

    Returns:
        str:
        The name of the app.
    """
    app_config = get_app_config_for_app(app)

    return app_config.name


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
    app_names_modules = [
        (app_config.name, app_config.module)
        for app_config in apps.get_app_configs()
    ]

    for (app_name, app_module) in app_names_modules:
        if module_has_submodule(app_module, 'management'):
            import_module('.management', app_name)


def register_app(app_label, app):
    """Register a new app in the registry.

    This must be balanced with a :py:func:`unregister_app` call.

    Version Changed:
        3.0:
        Moved from ``django.compat.apps``.

    Args:
        app_label (str):
            The label of the app.

        app (module):
            The app module.
    """
    app_config = AppConfig(app.__name__, app)
    app_config.label = app_label
    app_config.models_module = app

    apps.set_installed_apps(settings.INSTALLED_APPS + [app_config])


def unregister_app(app_label):
    """Unregister an app in the registry.

    This must be balanced with a :py:func:`register_app` call.

    Version Changed:
        3.0:
        Moved from ``django.compat.apps``.

    Args:
        app_label (str):
            The label of the app to register.
    """
    # We need to balance the ``set_installed_apps`` from
    # :py:func:`register_app` here.
    apps.unset_installed_apps()

    all_models[app_label].clear()
    apps.clear_cache()


def register_app_models(app_label, model_infos, reset=False):
    """Register one or more models to a given app.

    These will add onto the list of existing models.

    Version Changed:
        3.0:
        Moved from ``django.compat.apps``.

    Args:
        app_label (str):
            The label of the app to register the models on.

        model_info (list);
            A list of pairs of ``(model name, model class)`` to register.

        reset (bool, optional):
            If set, the old list will be overwritten with the new list.
    """
    if app_label not in all_models:
        # This isn't really needed for Django 1.7+ (which uses defaultdict
        # with OrderedDict), but it's needed for earlier versions, so do it
        # explicitly.
        all_models[app_label] = OrderedDict()

    model_dict = all_models[app_label]

    if reset:
        model_dict.clear()

    for model_name, model in model_infos:
        model_dict[model_name] = model

    apps.clear_cache()


def unregister_app_model(app_label, model_name):
    """Unregister a model with the given name from the given app.

    Version Changed:
        3.0:
        Moved from ``django.compat.apps``.

    Args:
        app_label (str):
            The label of the app containing a model.

        model_name (str):
            The name of the model to unregister.
    """
    del all_models[app_label][model_name]
    apps.clear_cache()

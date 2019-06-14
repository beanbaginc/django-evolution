"""Compatibility functions for the application registration.

This provides functions for app registration and lookup. These functions
translate to the various versions of Django that are supported.
"""

from __future__ import unicode_literals

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

try:
    # Django >= 1.7
    from django.apps.config import AppConfig
    from django.apps.registry import apps

    cache = None
except ImportError:
    # Django < 1.7
    from django.db.models.loading import cache

    apps = None
    AppConfig = None

from django_evolution.compat.datastructures import OrderedDict
from django_evolution.compat.models import all_models


def get_app(app_label, emptyOK=False):
    """Return the app with the given label.

    This returns the app from the app registry on Django >= 1.7, and from
    the old-style cache on Django < 1.7.

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
    if apps:
        # Django >= 1.7
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
    else:
        # Django < 1.7
        return cache.get_app(app_label, emptyOK)


def get_apps():
    """Return the list of all installed apps with models.

    This returns the apps from the app registry on Django >= 1.7, and from
    the old-style cache on Django < 1.7.

    Returns:
        list: A list of all the modules containing model classes.
    """
    if apps:
        # Django >= 1.7
        return [
            app.models_module
            for app in apps.get_app_configs()
            if app.models_module is not None
        ]
    else:
        # Django < 1.7
        return cache.get_apps()


def is_app_registered(app):
    """Return whether the app registry is tracking a given app.

    Args:
        app (module):
            The app to check for.

    Returns:
        bool:
        ``True`` if the app is tracked by the registry. ``False`` if not.
    """
    if apps:
        # Django >= 1.7
        return apps.is_installed(app.__name__)
    else:
        # Django < 1.7
        return app in cache.app_store


def register_app(app_label, app):
    """Register a new app in the registry.

    This must be balanced with a :py:func:`unregister_app` call.

    Args:
        app_label (str):
            The label of the app.

        app (module):
            The app module.
    """
    if apps:
        # Django >= 1.7
        app_config = AppConfig(app.__name__, app)
        app_config.label = app_label
        app_config.models_module = app

        apps.set_installed_apps(settings.INSTALLED_APPS + [app_config])
    else:
        # Django < 1.7
        cache.app_store[app] = len(cache.app_store)

        if hasattr(cache, 'app_labels'):
            cache.app_labels[app_label] = app


def unregister_app(app_label):
    """Unregister an app in the registry.

    This must be balanced with a :py:func:`register_app` call.

    Args:
        app_label (str):
            The label of the app to register.
    """
    if apps:
        # Django >= 1.7
        #
        # We need to balance the ``set_installed_apps`` from
        # :py:func:`register_app` here.
        apps.unset_installed_apps()

    all_models[app_label].clear()
    clear_app_cache()


def register_app_models(app_label, model_infos, reset=False):
    """Register one or more models to a given app.

    These will add onto the list of existing models.

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

    clear_app_cache()


def unregister_app_model(app_label, model_name):
    """Unregister a model with the given name from the given app.

    Args:
        app_label (str):
            The label of the app containing a model.

        model_name (str):
            The name of the model to unregister.
    """
    del all_models[app_label][model_name]
    clear_app_cache()


def clear_app_cache():
    """Clear the Django app/models caches.

    This cache is used in Django >= 1.2 to quickly return results when
    fetching models. It needs to be cleared when modifying the model registry.
    """
    if apps:
        # Django >= 1.7
        apps.clear_cache()
    elif hasattr(cache, '_get_models_cache'):
        # Django >= 1.2, < 1.7
        cache._get_models_cache.clear()


__all__ = [
    'apps',
    'clear_app_cache',
    'get_app',
    'get_apps',
]

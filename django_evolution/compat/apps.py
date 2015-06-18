try:
    from django.apps.registry import apps

    # Django >= 1.7
    get_apps = apps.get_apps
    cache = None
except ImportError:
    from django.db.models.loading import cache

    # Django < 1.7
    get_apps = cache.get_apps
    apps = None


def get_app(app_label, emptyOK=False):
    """Return the app with the given label.

    This returns the app from the app registry on Django >= 1.7, and from
    the old-style cache on Django < 1.7.

    The ``emptyOK`` argument is ignored for Django >= 1.7.
    """
    if apps:
        return apps.get_app(app_label)
    else:
        return cache.get_app(app_label, emptyOK)


__all__ = ['get_app', 'get_apps']

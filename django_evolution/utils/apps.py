"""Utilities for working with apps."""

from __future__ import unicode_literals


def get_app_label(app):
    """Return the label of an app.

    Args:
        app (module):
            The app.

    Returns:
        str:
        The label of the app.
    """
    return app.__name__.split('.')[-2]


def get_app_name(app):
    """Return the name of an app.

    Args:
        app (module):
            The app.

    Returns:
        str:
        The name of the app.
    """
    return '.'.join(app.__name__.split('.')[:-1])

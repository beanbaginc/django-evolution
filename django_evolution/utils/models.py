"""Utilities for working with models."""

from __future__ import unicode_literals

from django.db import router

from django_evolution.compat.models import get_model


def get_database_for_model_name(app_name, model_name):
    """Return the database used for a given model.

    Given an app name and a model name, this will return the proper
    database connection name used for making changes to that model. It
    will go through any custom routers that understand that type of model.

    Args:
        app_name (unicode):
            The name of the app owning the model.

        model_name (unicode):
            The name of the model.

    Returns:
        unicode:
        The name of the database used for the model.
    """
    return router.db_for_write(get_model(app_name, model_name))

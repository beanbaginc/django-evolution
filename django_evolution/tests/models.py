# This module is used as a placeholder for the registration of test models.
# It is intentionally empty; individual tests create and register models
# that will appear to Django as if they are in this module.
from __future__ import unicode_literals

from django.db import models


class BaseTestModel(models.Model):
    """Base class for test-created models.

    This is intended to be used for all models that are created during unit
    test runs. It sets the appropriate app to ensure that models aren't
    grouped under the ``django_evolution`` app.
    """

    class Meta:
        abstract = True
        app_label = 'tests'

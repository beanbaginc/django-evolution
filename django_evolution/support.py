from __future__ import unicode_literals

from django.db.models.options import Options

try:
    # Django >= 1.7
    from django import apps
except ImportError:
    # Django < 1.7
    apps = None


_options = Options({})


# Index names changed in Django 1.5, with the introduction of index_together.
supports_index_together = hasattr(_options, 'index_together')


# Django 1.11 introduced formal support for defining explicit indexes not
# bound to a field definition or as part of index_together/unique_together.
supports_indexes = hasattr(_options, 'indexes')


#: Whether built-in support for Django Migrations is present.
#:
#: This is available in Djagno 1.7+.
supports_migrations = apps is not None

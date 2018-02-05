from django.db.models.options import Options


_options = Options({})


# Index names changed in Django 1.5, with the introduction of index_together.
supports_index_together = hasattr(_options, 'index_together')


# Django 1.11 introduced formal support for defining explicit indexes not
# bound to a field definition or as part of index_together/unique_together.
supports_indexes = hasattr(_options, 'indexes')

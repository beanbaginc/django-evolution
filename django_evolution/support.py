from django.db.models.options import Options

try:
    from django.db import connections
    supports_multi_db = True
except ImportError:
    supports_multi_db = False


_options = Options({})


# 'through' tables for ManyToManyFields are auto-created.
autocreate_through_tables = hasattr(_options, 'auto_created')

# This is not a great check, but it's from the same version as auto-created
# tables (Django 1.2), so we use it.
digest_index_names = hasattr(_options, 'auto_created')

# Index names changed in Django 1.5, with the introduction of index_together.
supports_index_together = hasattr(_options, 'index_together')

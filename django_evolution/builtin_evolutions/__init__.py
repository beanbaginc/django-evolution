from __future__ import unicode_literals


BUILTIN_SEQUENCES = {
    'django.contrib.admin': ['admin_move_to_migrations'],
    'django.contrib.auth': [],
    'django.contrib.contenttypes': [],
    'django.contrib.flatpages': ['flatpages_move_to_migrations'],
    'django.contrib.redirects': ['redirects_move_to_migrations'],
    'django.contrib.sessions': [],
    'django.contrib.sites': ['sites_move_to_migrations'],
}


# Starting in Django 1.3 alpha, Session.expire_date has a db_index set.
# This needs to be reflected in the evolutions. Rather than hard-coding
# a specific version to check for, we check the actual value in the field.
try:
    from django.contrib.sessions.models import Session

    if Session._meta.get_field('expire_date').db_index:
        BUILTIN_SEQUENCES['django.contrib.sessions'].append(
            'session_expire_date_db_index')
except RuntimeError:
    # The model was not included in INSTALLED_APPS, most likely. Skip it.
    pass

# Starting in Django 1.4 alpha, the Message model was deleted.
try:
    from django.contrib.auth.models import Message
except ImportError:
    BUILTIN_SEQUENCES['django.contrib.auth'].append('auth_delete_message')
except RuntimeError:
    # The model was not included in INSTALLED_APPS, most likely. Skip it.
    pass


# Starting with Django Evolution 0.7.0, we explicitly need ChangeMetas for
# unique_together.
BUILTIN_SEQUENCES['django.contrib.auth'] += [
    'auth_unique_together_baseline',
    'auth_move_to_migrations',
]
BUILTIN_SEQUENCES['django.contrib.contenttypes'] += [
    'contenttypes_unique_together_baseline',
    'contenttypes_move_to_migrations',
]
BUILTIN_SEQUENCES['django.contrib.sessions'] += [
    'sessions_move_to_migrations',
]

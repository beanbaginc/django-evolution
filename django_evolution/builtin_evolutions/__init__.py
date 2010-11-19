from django.contrib.sessions.models import Session


BUILTIN_SEQUENCES = {
    'django.contrib.sessions': []
}


# Starting in Django 1.3 alpha, Session.expire_date has a db_index set.
# This needs to be reflected in the evolutions. Rather than hard-coding
# a specific version to check for, we check the actual value in the field.
if Session._meta.get_field_by_name('expire_date')[0].db_index:
    BUILTIN_SEQUENCES['django.contrib.sessions'].append(
        'session_expire_date_db_index')

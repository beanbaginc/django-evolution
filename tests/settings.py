from __future__ import print_function, unicode_literals

import os
import sys

from django.core.exceptions import ImproperlyConfigured


DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {},
    'db_multi': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'django_evolution_test_multi.db',
    },
}

TEST_DATABASES = {
    'default': {},
    'sqlite3': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'django_evolution_test.db',
    },
}

from default_test_db_settings import TEST_DATABASES as NEW_TEST_DATABASES
TEST_DATABASES.update(NEW_TEST_DATABASES)

try:
    from test_db_settings import TEST_DATABASES as NEW_TEST_DATABASES
    TEST_DATABASES.update(NEW_TEST_DATABASES)
except ImportError:
    # There are no custom settings.
    pass

TEST_DB_CHOICE = os.getenv('DJANGO_EVOLUTION_TEST_DB', 'sqlite3')

try:
    DATABASES['default'] = TEST_DATABASES[TEST_DB_CHOICE]
except KeyError:
    raise ImproperlyConfigured(
        'Requested database type "%s" is not a valid choice.'
        % db_choice)


# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Chicago'
USE_TZ = True

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = ''

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'af=y9ydd51a0g#bevy0+p#(7ime@m#k)$4$9imoz*!rl97w0j0'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
#     'django.template.loaders.eggs.load_template_source',
)

MIDDLEWARE_CLASSES = (
)

ROOT_URLCONF = 'urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django_evolution',

    # The following are needed for some tests.
    'django_evolution.tests.app_deps_app',
    'django_evolution.tests.evolution_deps_app',
    'django_evolution.tests.evolutions_app',
    'django_evolution.tests.evolutions_app2',
    'django_evolution.tests.no_models_app',
    'django_evolution.tests.migrations_app',
    'django_evolution.tests.migrations_app2',
]

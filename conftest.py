"""Configures pytest and Django environment setup for Django Evolution."""

from __future__ import unicode_literals

import os
import sqlite3
import sys

import django
import pytest

try:
    from MySQLdb.release import __version__ as mysql_version
except ImportError:
    mysql_version = None

try:
    import psycopg2
except ImportError:
    psycopg2 = None


top_dir = os.path.dirname(__file__)
sys.path.insert(0, top_dir)
sys.path.insert(0, os.path.join(top_dir, 'tests'))


def pytest_addoption(parser):
    """Add options for pytest.

    Args:
        parser (object):
            pytest's argument parser.
    """
    try:
        from test_db_settings import TEST_DATABASES
    except ImportError:
        pytest.exit('Missing test_db_settings.py This is needed for '
                    'non-sqlite unit tests.')

    parser.addoption(
        '--db',
        action='store',
        default='sqlite3',
        choices=sorted(TEST_DATABASES.keys()),
        help=(
            'A database name to test (defined in your '
            'tests/test_db_settings.py)'
        ))


class DjangoSetupPlugin(object):
    """Plugin to manage Django setup specific to Django Evolution.

    This will set up Django, covering a range of Django versions.

    A database will be set up and torn down based on the database name
    specified in :option:`--db`.
    """

    def __init__(self, config):
        """Initialize the plugin.

        Args:
            config (object):
                The configuration object.
        """
        self.config = config
        self.old_db_names = None

    def pytest_sessionstart(self, session):
        """Start a pytest session.

        This will set up the database and Django settings to use for the
        tests.

        Args:
            session (pytest.Session):
                The session that's starting.
        """
        config = session.config

        os.environ.update({
            'DJANGO_SETTINGS_MODULE': 'tests.settings',
            'DJANGO_EVOLUTION_TEST_DB': config.option.db,
        })

        # Ensure that all Django Evolution patches are applied for Django.
        from django_evolution.compat.patches import apply_patches
        apply_patches()

        from django.conf import settings
        from django.core import management
        from django.db import connections
        from django.test.utils import setup_test_environment

        if hasattr(django, 'setup'):
            # Django >= 1.7
            django.setup()

        setup_test_environment()
        settings.DEBUG = False

        old_db_names = []
        verbosity = config.option.verbose

        for alias in connections:
            connection = connections[alias]

            old_db_names.append((connection, connection.settings_dict['NAME']))
            connection.creation.create_test_db(verbosity,
                                               autoclobber=True)

        self.old_db_names = old_db_names

        if django.VERSION[:2] >= (1, 7):
            management.call_command('migrate',
                                    verbosity=verbosity,
                                    interactive=False)
        else:
            management.call_command('syncdb',
                                    verbosity=verbosity,
                                    interactive=False)

    def pytest_sessionfinish(self, *args, **kwargs):
        """Finish a pytest session.

        This will tear down and destroy the databases and test environment.

        Args:
            *args (tuple, unused):
                Positional arguments passed to the hook.

            **kwargs (dict, unused):
                Keyword arguments passed to the hook.
        """
        from django.test.utils import teardown_test_environment

        for connection, name in self.old_db_names:
            connection.creation.destroy_test_db(name, verbosity=0)

        teardown_test_environment()


@pytest.hookimpl
def pytest_configure(config):
    """Configure pytest.

    This will set up our Django plugin.

    Args:
        config (object):
            The pytest configuration object.
    """
    config.pluginmanager.register(DjangoSetupPlugin(config), 'django-setup')


def pytest_report_header(config):
    """Return information for the report header.

    This will log the version of Django, SQLite, MySQL, and Postgres, along
    with the database that will be used for testing.

    Args:
        config (object):
            The pytest configuration object.

    Returns:
        list of unicode:
        The report header entries to log.
    """
    header = [
        'Django %s' % django.get_version(),
        'SQLite %s' % sqlite3.sqlite_version,
    ]

    if mysql_version is not None:
        header.append('MySQLdb %s' % mysql_version)

    if psycopg2 is not None:
        header.append('Psycopg2 %s' % psycopg2.__version__)

    header.append('Testing with database: %s'
                  % os.environ.get('DJANGO_EVOLUTION_TEST_DB'))

    return header

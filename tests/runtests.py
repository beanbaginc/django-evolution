#!/usr/bin/env python

from __future__ import print_function, unicode_literals

import nose
import os
import sqlite3
import sys

import django

try:
    from MySQLdb.release import __version__ as mysql_version
except ImportError:
    mysql_version = None

try:
    import psycopg2
except ImportError:
    pyscopg2 = None


def run_tests(verbosity=1, interactive=False):
    from django.conf import settings
    from django.core import management
    from django.db import connections
    from django.test.utils import setup_test_environment, \
                                  teardown_test_environment

    if hasattr(django, 'setup'):
        # Django >= 1.7
        django.setup()

    setup_test_environment()
    settings.DEBUG = False

    old_db_names = []

    for alias in connections:
        connection = connections[alias]

        old_db_names.append((connection, connection.settings_dict['NAME']))
        connection.creation.create_test_db(verbosity,
                                           autoclobber=not interactive)

    if django.VERSION[:2] >= (1, 7):
        management.call_command('migrate', verbosity=verbosity,
                                interactive=interactive)
    else:
        management.call_command('syncdb', verbosity=verbosity,
                                interactive=interactive)

    nose_argv = [
        'runtests.py',
        '-v',
        '--with-coverage',
        '--with-doctest',
        '--doctest-extension=.txt',
        '--cover-package=django_evolution',
        '--match=tests[\/]*.py',
        '--match=^test',
        '--exclude-dir=django_evolution/tests/db',
    ]

    if len(sys.argv) > 2:
        nose_argv += sys.argv[2:]

    result = nose.main(argv=nose_argv, exit=False)

    for connection, name in old_db_names:
        connection.creation.destroy_test_db(name, verbosity=0)

    teardown_test_environment()

    if result.success:
        return 0
    else:
        return 1


if __name__ == "__main__":
    os.chdir(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, os.getcwd())
    os.environ['DJANGO_SETTINGS_MODULE'] = "tests.settings"

    if len(sys.argv) > 1:
        os.environ['DJANGO_EVOLUTION_TEST_DB'] = sys.argv[1]

    # Show some useful version information.
    print('Python %s.%s.%s' % sys.version_info[:3])
    print('Django %s' % django.get_version())
    print('SQLite %s' % sqlite3.sqlite_version)

    if mysql_version is not None:
        print('MySQLdb %s' % mysql_version)

    if psycopg2 is not None:
        print('Psycopg2 %s' % psycopg2.__version__)

    print()

    sys.exit(run_tests())

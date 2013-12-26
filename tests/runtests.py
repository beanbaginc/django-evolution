#!/usr/bin/env python
import nose
import os
import sys


def run_tests(verbosity=1, interactive=False):
    from django.conf import settings
    from django.core import management
    from django.db import connections
    from django.test.utils import setup_test_environment, \
                                  teardown_test_environment

    setup_test_environment()
    settings.DEBUG = False

    old_db_names = []

    for alias in connections:
        connection = connections[alias]

        old_db_names.append((connection, connection.settings_dict['NAME']))
        connection.creation.create_test_db(verbosity,
                                           autoclobber=not interactive)

    management.call_command('syncdb', verbosity=verbosity,
                            interactive=interactive)

    nose_argv = ['runtests.py', '-v',
                 '--with-coverage',
                 '--with-doctest',
                 '--doctest-extension=.txt',
                 '--cover-package=django_evolution',
                 '--match=tests[\/]*.py',
                 '--match=^test']

    if len(sys.argv) > 2:
        nose_argv += sys.argv[2:]

    nose.run(argv=nose_argv)

    for connection, name in old_db_names:
        connection.creation.destroy_test_db(name, verbosity=0)

    teardown_test_environment()


if __name__ == "__main__":
    os.chdir(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, os.getcwd())
    os.environ['DJANGO_SETTINGS_MODULE'] = "tests.settings"

    if len(sys.argv) > 1:
        os.environ['DJANGO_EVOLUTION_TEST_DB'] = sys.argv[1]

    run_tests()

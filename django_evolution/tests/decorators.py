"""Decorators to aid in creating unit tests.

Version Added:
    2.1
"""

from __future__ import unicode_literals

from functools import wraps
from unittest import SkipTest

import django

from django_evolution.support import (supports_constraints,
                                      supports_index_together,
                                      supports_indexes,
                                      supports_migrations)


def _build_requires_support_decorator(flag, skip_message):
    """Build a decorator checking for Django support for a feature.

    Args:
        flag (bool):
            The support flag to check.

        skip_message (unicode):
            The skip message. This should have ``%(django_version)s`` in the
            message somewhere.

    Raises:
        unittest.SkipTest:
            Raised if run on a version of Django without the required support.
    """
    def _decorator(func):
        @wraps(func)
        def _wrapper(*args, **kwargs):
            if not flag:
                raise SkipTest(skip_message % {
                    'django_version': '%s.%s' % django.VERSION[:2],
                })

            return func(*args, **kwargs)

        return _wrapper

    return _decorator


#: Decorator to require Meta.constraints support for running a test.
#:
#: Args:
#:     func (callable):
#:         The unit test function to wrap.
#:
#: Raises:
#:     unittest.SkipTest:
#:         The current version of Django doesn't support ``Meta.constraints``.
requires_meta_constraints = _build_requires_support_decorator(
    flag=supports_constraints,
    skip_message=("Meta.constraints isn't supported on Django "
                  "%(django_version)s"))


#: Decorator to require Meta.index_together support for running a test.
#:
#: Args:
#:     func (callable):
#:         The unit test function to wrap.
#:
#: Raises:
#:     unittest.SkipTest:
#:         The current version of Django doesn't support
#:         ``Meta.index_together``.
requires_meta_index_together = _build_requires_support_decorator(
    flag=supports_index_together,
    skip_message=("Meta.index_together isn't supported on Django "
                  "%(django_version)s"))


#: Decorator to require Meta.indexes support for running a test.
#:
#: Args:
#:     func (callable):
#:         The unit test function to wrap.
#:
#: Raises:
#:     unittest.SkipTest:
#:         The current version of Django doesn't support ``Meta.indexes``.
requires_meta_indexes = _build_requires_support_decorator(
    flag=supports_indexes,
    skip_message="Meta.indexes isn't supported on Django %(django_version)s")


#: Decorator to require migrations support for running a test.
#:
#: Args:
#:     func (callable):
#:         The unit test function to wrap.
#:
#: Raises:
#:     unittest.SkipTest:
#:         The current version of Django doesn't support migrations.
requires_migrations = _build_requires_support_decorator(
    flag=supports_migrations,
    skip_message="Migrations aren't supported on Django %(django_version)s")


#: Decorator to require migration history checks for running a test.
#:
#: Args:
#:     func (callable):
#:         The unit test function to wrap.
#:
#: Raises:
#:     unittest.SkipTest:
#:         The current version of Django doesn't support performing history
#:         checks when running migrations.
requires_migration_history_checks = _build_requires_support_decorator(
    flag=(django.VERSION >= (1, 10)),
    skip_message=("Migration history checks aren't supported on Django "
                  "%(django_version)s"))

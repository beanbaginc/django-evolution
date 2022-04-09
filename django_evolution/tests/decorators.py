"""Decorators to aid in creating unit tests.

Version Added:
    2.1
"""

from __future__ import unicode_literals

import inspect
from functools import wraps
from unittest import SkipTest

import django
from django.db import models

from django_evolution.support import (supports_constraints,
                                      supports_index_feature,
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


#: Decorator to require expressions support in Meta.indexes for running a test.
#:
#: Args:
#:     func (callable):
#:         The unit test function to wrap.
#:
#: Raises:
#:     unittest.SkipTest:
#:         The current version of Django doesn't support expressions in
#:         ``Meta.indexes``.
requires_index_expressions = _build_requires_support_decorator(
    flag=supports_index_feature('expressions'),
    skip_message=("Index doesn't support expressions on Django "
                  "%(django_version)s"))


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


def requires_attr(cls, attr_name):
    """Require an attribute on a class for a test to run.

    Version Added:
        2.2

    Args:
        cls (type):
            The class to check.

        attr_name (unicode):
            The name of the attribute to require on the class.

    Raises:
        unittest.SkipTest:
            The attribute is missing. The test will be skipped with a suitable
            message.
    """
    return _build_requires_support_decorator(
        flag=cls is not None and hasattr(cls, attr_name),
        skip_message=("%s.%s isn't supported on Django %%(django_version)s"
                      % (cls.__name__, attr_name)))


def requires_model_field(field_name):
    """Require the existence of a Django field for a test to run.

    Version Added:
        2.2

    Args:
        field_name (unicode):
            The name of the field to require.

    Raises:
        unittest.SkipTest:
            The field is missing. The test will be skipped with a suitable
            message.
    """
    return _build_requires_support_decorator(
        flag=hasattr(models, field_name),
        skip_message=("models.%s isn't supported on Django %%(django_version)s"
                      % field_name))


def requires_index_feature(feature_name):
    """Require a feature on the Index class.

    Version Added:
        2.2

    Args:
        feature_name (unicode):
            The name of the Index feature to require.

    Raises:
        unittest.SkipTest:
            The attribute is missing. The test will be skipped with a suitable
            message.
    """
    return _build_requires_support_decorator(
        flag=supports_index_feature(feature_name),
        skip_message=("Index.%s isn't supported on Django %%(django_version)s"
                      % feature_name))


def requires_param(cls_or_func, param_name, label=None):
    """Require a parameter in a function or constructor for a test to run.

    Version Added:
        2.2

    Args:
        cls_or_func (type or callable):
            The class or function requiring the parameter.

        param_name (unicode):
            The name of the parameter on the function.

        label (unicode, optional):
            An explicit label to show instead of the parameter name in the
            skip message.

    Raises:
        unittest.SkipTest:
            The parameter is missing. The test will be skipped with a suitable
            message.
    """
    if cls_or_func is None:
        return _build_requires_support_decorator(
            flag=False,
            skip_message=("A class or function required for this test isn't "
                          "available on Django %%(django_version)s"))

    if inspect.isclass(cls_or_func):
        func = cls_or_func.__init__
    else:
        func = cls_or_func

    if hasattr(inspect, 'getfullargspec'):
        # Python 3.x
        argspec = inspect.getfullargspec(func)
        arg_varargs = argspec.varargs
        arg_names = argspec.args
        kwarg_names = argspec.kwonlyargs
    else:
        # Python 2.x
        argspec = inspect.getargspec(func)
        arg_varargs = argspec.varargs
        arg_names = argspec.args
        kwarg_names = argspec.keywords

    if param_name == '*':
        flag = arg_varargs is not None
    else:
        flag = ((arg_names and param_name in arg_names) or
                (kwarg_names and param_name in kwarg_names))

    return _build_requires_support_decorator(
        flag=flag,
        skip_message=("%s(%s=...) isn't supported on Django "
                      "%%(django_version)s"
                      % (cls_or_func.__name__, label or param_name)))

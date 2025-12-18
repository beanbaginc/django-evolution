"""Constants indicating available Django features."""

from __future__ import annotations

from inspect import signature

from django.db.models import CheckConstraint, F, Q
from django.db.models.options import Options

try:
    # Django >= 1.7
    from django import apps
except ImportError:
    # Django < 1.7
    apps = None

try:
    # Django >= 1.11
    from django.db.models import Index
    _test_index = Index(fields=['test'])
except ImportError:
    Index = None
    _test_index = None


_options = Options({})


#: Index names changed in Django 1.5, with the introduction of index_together.
#:
#: This field was deprecated in Django 4.2 and removed in 5.1.
supports_index_together = hasattr(_options, 'index_together')


#: Whether new-style Index classes are available.
#:
#: Django 1.11 introduced formal support for defining explicit indexes not
#: bound to a field definition or as part of
#: ``index_together``/``unique_together``.
#:
#: Type:
#:     bool
supports_indexes = hasattr(_options, 'indexes')


#: Whether Q() objects can be directly compared.
#:
#: Django 2.0 introduced this support.
#:
#: Type:
#:     bool
supports_q_comparison = hasattr(Q, '__eq__')

#: Whether F() objects can be directly compared.
#:
#: Django 2.0 introduced this support.
#:
#: Type:
#:     bool
supports_f_comparison = hasattr(F, '__eq__')


#: Whether new-style Constraint classes are available.
#:
#: Django 2.2 introduced formal support for defining explicit constraints not
#: bound to a field definition.
supports_constraints = hasattr(_options, 'constraints')


#: Whether database table comments are available.
#:
#: Django 4.2 introduced formal support for setting comments attached to
#: tables.
#:
#: Support may vary by database backend.
#:
#: Version Added:
#:     2.3
#:
#: Type:
#:     bool
supports_db_table_comments = hasattr(_options, 'db_table_comment')


#: Whether built-in support for Django Migrations is present.
#:
#: This is available in Django 1.7+.
supports_migrations = apps is not None


def supports_index_feature(attr_name):
    """Return whether Index supports a specific attribute.

    Args:
        attr_name (unicode):
            The name of the attribute.

    Returns:
        bool:
        ``True`` if the attribute is supported on this version of Django.
        ``False`` if it is not.
    """
    return supports_indexes and hasattr(_test_index, attr_name)


#: Whether CheckConstraint uses ``condition``.
#:
#: Django 5.1 introduced ``CheckConstraint.condition`` and deprecated
#: ``CheckConstraint.check``.
#:
#: Version Added:
#:     3.0
check_constraint_uses_condition = (
    'condition' in signature(CheckConstraint.__init__).parameters)

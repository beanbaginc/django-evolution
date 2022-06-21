"""Patch to bring back deprecated classes in the collections module.

The :py:mod:`collections` module had several classes that were moved into
:py:mod:`collections.abc`. The old imports were deprecated and then removed
in Python 3.10. Django 2.0 and older still used these old locations, so on
those versions, :py:mod:`collections` must be patched.

Version Added:
    2.1.3
"""

from __future__ import unicode_literals

import collections

import django


def needs_patch():
    """Return whether the collections module needs to be patched.

    This will check if the :py:mod:`collections` module has one of the
    deprecated classes removed in Python 3.10. If it does not, the patch
    will be applied.

    Returns:
        bool:
        ``True`` if the module needs to be patched. ``False`` if it does not.
    """
    return (django.VERSION[:2] <= (2, 0) and
            not hasattr(collections, 'Callable'))


def apply_patch():
    """Apply a patch to the collections module.

    This will patch the :py:mod:`collections` module to bring back many of the
    imports that were removed in Python 3.10.
    """
    collections.Callable = collections.abc.Callable
    collections.Iterable = collections.abc.Iterable
    collections.Iterator = collections.abc.Iterator
    collections.Mapping = collections.abc.Mapping
    collections.MutableMapping = collections.abc.MutableMapping
    collections.Sequence = collections.abc.Sequence

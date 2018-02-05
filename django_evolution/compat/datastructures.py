"""Compatibility imports for data structures.

This provides imports for data structures that are needed internally, to
provide compatibility with different versions of Django.
"""

from __future__ import unicode_literals

try:
    from collections import OrderedDict
except ImportError:
    # Only available on Django < 1.9.
    from django.utils.datastructures import SortedDict as OrderedDict


__all__ = [
    'OrderedDict',
]

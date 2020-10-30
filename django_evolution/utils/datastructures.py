"""Utilities for working with data structures.

Version Added:
    2.1
"""

from __future__ import unicode_literals

from collections import OrderedDict

from django_evolution.compat import six


def filter_dup_list_items(items):
    """Return list items with duplicates filtered out.

    The order of items will be preserved, but only the first occurrence of
    any given item will remain in the list.

    Version Added:
        2.1

    Args:
        items (list):
            The list of items.

    Returns:
        list:
        The resulting de-duplicated list of items.
    """
    return list(six.iterkeys(OrderedDict(
        (item, True)
        for item in items
    )))


def merge_dicts(dest, source):
    """Merge two dictionaries together.

    This will recursively merge a source dictionary into a destination
    dictionary with the following rules:

    * Any keys in the source that aren't in the destination will be placed
      directly to the destination (using the same instance of the value, not
      a copy).
    * Any lists that are in both the source and destination will be combined
      by appending the source list to the destinataion list (and this will not
      recurse into lists).
    * Any dictionaries that are in both the source and destinataion will be
      merged using this function.
    * Any keys that are not a list or dictionary that exist in both
      dictionaries will result in a :py:exc:`TypeError`.

    Version Added:
        2.1

    Args:
        dest (dict):
            The destination dictionary to merge into.

        source (dict):
            The source dictionary to merge into the destination.

    Raises:
        TypeError:
            A key was present in both dictionaries with a type that could not
            be merged.
    """
    for key, value in six.iteritems(source):
        if key in dest:
            if isinstance(value, list):
                if not isinstance(dest[key], list):
                    raise TypeError(
                        'Cannot merge a list into a %r for key "%s".'
                        % (type(dest[key]), key))

                dest[key] += value
            elif isinstance(value, dict):
                if not isinstance(dest[key], dict):
                    raise TypeError(
                        'Cannot merge a dictionary into a %r for key "%s".'
                        % (type(dest[key]), key))

                merge_dicts(dest[key], value)
            else:
                raise TypeError(
                    'Key "%s" was not an expected type (found %r) '
                    'when merging dictionaries.'
                    % (key, type(value)))
        else:
            dest[key] = value

"""Compatibility functions for Python 2 and 3."""

from __future__ import unicode_literals

from django.utils import six
from django.utils.six.moves import cPickle as pickle


def pickle_dumps(obj):
    """Return a pickled representation of an object.

    This will always use Pickle protocol 0, which is the default on Python 2,
    for compatibility across Python 2 and 3.

    Args:
        obj (object):
            The object to dump.

    Returns:
        bytes:
        The pickled representation of the object.
    """
    return pickle.dumps(obj, protocol=0)


def pickle_loads(pickled_str):
    """Return the unpickled data from a pickle payload.

    Args:
        pickled_str (bytes):
            The pickled data.

    Returns:
        object:
        The unpickled data.
    """
    if isinstance(pickled_str, six.text_type):
        pickled_str = pickled_str.encode('latin1')

    return pickle.loads(pickled_str)

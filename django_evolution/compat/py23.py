"""Compatibility functions for Python 2 and 3."""

from __future__ import unicode_literals

import io

from django_evolution.compat import six
from django_evolution.compat.picklers import DjangoCompatUnpickler
from django_evolution.compat.six.moves import cPickle as pickle


def pickle_dumps(obj):
    """Return a pickled representation of an object.

    This will always use Pickle protocol 0, which is the default on Python 2,
    for compatibility across Python 2 and 3.

    Args:
        obj (object):
            The object to dump.

    Returns:
        unicode:
        The Unicode pickled representation of the object, safe for storing
        in the database.
    """
    return pickle.dumps(obj, protocol=0).decode('latin1')


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

    try:
        return pickle.loads(pickled_str)
    except AttributeError:
        # We failed to load something from the pickled data. We have to try
        # again with our own unpickler, which unfortunately won't benefit from
        # cPickle, but it at least lets us remap things.
        return DjangoCompatUnpickler(io.BytesIO(pickled_str)).load()

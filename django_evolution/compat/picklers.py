"""Compatibility methods for pickle operations."""

from __future__ import annotations

import io
import pickle

from django_evolution.compat.datastructures import OrderedDict
from django_evolution.conf import django_evolution_settings


class SortedDict(dict):
    """Compatibility for unpickling a SortedDict.

    Old signatures may use an old Django ``SortedDict`` structure, which does
    not exist in modern versions. This changes any construction of this
    data structure into a :py:class:`collections.OrderedDict`.
    """

    def __new__(cls, *args, **kwargs):
        """Construct an instance of the class.

        Args:
            *args (tuple):
                Positional arguments to pass to the constructor.

            **kwargs (dict):
                Keyword arguments to pass to the constructor.

        Returns:
            collections.OrderedDict:
            The new instance.
        """
        return OrderedDict.__new__(cls, *args, **kwargs)


class DjangoCompatUnpickler(pickle._Unpickler):
    """Unpickler compatible with changes to Django class/module paths.

    This provides compatibility across Django versions for various field types,
    updating referenced module paths for fields to a standard location so
    that the fields can be located on all Django versions.
    """

    def find_class(self, module, name):
        """Return the class for a given module and class name.

        If looking up a class from ``django.db.models.fields``, the class will
        instead be looked up from ``django.db.models``, fixing lookups on
        some Django versions.

        Args:
            module (unicode):
                The module path.

            name (unicode):
                The class name.

        Returns:
            type:
            The resulting class.

        Raises:
            AttributeError:
                The class could not be found in the module.
        """
        if module == 'django.utils.datastructures' and name == 'SortedDict':
            return SortedDict
        elif module == 'django.db.models.fields':
            module = 'django.db.models'
        else:
            renamed_types = django_evolution_settings.RENAMED_FIELD_TYPES
            field_type = '%s.%s' % (module, name)

            if field_type in renamed_types:
                module, name = renamed_types[field_type].rsplit('.', 1)

        return pickle._Unpickler.find_class(self, module, name)


def pickle_dumps(obj):
    """Return a pickled representation of an object.

    This will always use Pickle protocol 0, which is the default on Python 2,
    for compatibility across Python 2 and 3.

    Version Changed:
        3.0:
        Moved from :py:mod:`django_evolution.compat.py23`.

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

    Version Changed:
        3.0:
        Moved from :py:mod:`django_evolution.compat.py23`.

    Args:
        pickled_str (bytes):
            The pickled data.

    Returns:
        object:
        The unpickled data.
    """
    if isinstance(pickled_str, str):
        pickled_str = pickled_str.encode('latin1')

    try:
        return pickle.loads(pickled_str)
    except AttributeError:
        # We failed to load something from the pickled data. We have to try
        # again with our own unpickler, which unfortunately won't benefit from
        # cPickle, but it at least lets us remap things.
        return DjangoCompatUnpickler(io.BytesIO(pickled_str)).load()

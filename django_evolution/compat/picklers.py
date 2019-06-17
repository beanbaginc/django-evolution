"""Picklers for working with serialized data."""

from __future__ import unicode_literals

try:
    # Python 3.x
    from pickle import _Unpickler as Unpickler
except ImportError:
    # Python 2.x
    from pickle import Unpickler

from django_evolution.compat.datastructures import OrderedDict


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


class DjangoCompatUnpickler(Unpickler):
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

        return Unpickler.find_class(self, module, name)

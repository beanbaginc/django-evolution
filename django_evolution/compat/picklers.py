"""Picklers for working with serialized data."""

from __future__ import unicode_literals

import pickle


class DjangoCompatUnpickler(pickle.Unpickler):
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
        if module == 'django.db.models.fields':
            module = 'django.db.models'

        return super(DjangoCompatUnpickler, self).find_class(module, name)

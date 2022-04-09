"""Internal support for handling deprecations in Django Evolution.

The version-specific objects in this module are not considered stable between
releases, and may be removed at any point. The base objects are considered
stable.

Version Added:
    2.2
"""

from __future__ import unicode_literals

import warnings


class BaseRemovedInDjangoEvolutionWarning(DeprecationWarning):
    """Base class for a Django Evolution deprecation warning.

    All version-specific deprecation warnings inherit from this, allowing
    callers to check for Django Evolution deprecations without being tied to a
    specific version.

    Version Added:
        2.2
    """

    @classmethod
    def warn(cls, message, stacklevel=2):
        """Emit the deprecation warning.

        This is a convenience function that emits a deprecation warning using
        this class, with a suitable default stack level. Callers can provide
        a useful message and a custom stack level.

        Args:
            message (unicode):
                The message to show in the deprecation warning.

            stacklevel (int, optional):
                The stack level for the warning.
        """
        warnings.warn(message, cls, stacklevel=stacklevel + 1)


class RemovedInDjangoEvolution30Warning(BaseRemovedInDjangoEvolutionWarning):
    """Deprecations for features being removed in Django Evolution 3.0.

    Note that this class will itself be removed in Django Evolution 3.0. If you
    need to check against Django Evolution deprecation warnings, please see
    :py:class:`BaseRemovedInDjangoEvolutionWarning`.

    Version Added:
        2.2
    """


class RemovedInDjangoEvolution40Warning(BaseRemovedInDjangoEvolutionWarning):
    """Deprecations for features being removed in Django Evolution 4.0.

    Note that this class will itself be removed in Django Evolution 4.0. If you
    need to check against Django Evolution deprecation warnings, please see
    :py:class:`BaseRemovedInDjangoEvolutionWarning`. Alternatively, you can use
    the alias for this class, :py:data:`RemovedInNextDjangoEvolutionWarning`.

    Version Added:
        2.2
    """


#: Alias for deprecations in the next Django Evolution release.
RemovedInNextDjangoEvolutionWarning = RemovedInDjangoEvolution30Warning

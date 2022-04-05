"""Main interface for evolving applications.

Version Changed:
    2.2:
    The classes have all moved to nested modules, but this module will continue
    to provide forwarding imports.

.. autosummary::
   :nosignatures:

   ~django_evolution.evolve.base.BaseEvolutionTask
   ~django_evolution.evolve.evolver.Evolver
   ~django_evolution.evolve.evolve_app_task.EvolveAppTask
   ~django_evolution.evolve.purge_app_task.PurgeAppTask
"""

from __future__ import unicode_literals

import logging

from django_evolution.evolve.base import BaseEvolutionTask
from django_evolution.evolve.evolver import Evolver
from django_evolution.evolve.evolve_app_task import EvolveAppTask
from django_evolution.evolve.purge_app_task import PurgeAppTask


logger = logging.getLogger(__name__)


__all__ = (
    'BaseEvolutionTask',
    'Evolver',
    'EvolveAppTask',
    'PurgeAppTask',
    'logging',
)

__autodoc_excludes__ = __all__

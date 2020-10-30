.. _django-evolution-coderef:

===========================
Module and Class References
===========================

.. note::
   Most of the codebase should not be considered stable API, as many parts
   will change.

   The code documented here is a subset of the codebase. Backend database
   implementations and some internal modules are not included.


.. _public-python-api:

Public API
==========

.. autosummary::
   :toctree: python

   django_evolution
   django_evolution.consts
   django_evolution.errors
   django_evolution.evolve
   django_evolution.models
   django_evolution.mutations
   django_evolution.signals
   django_evolution.signature


.. _private-python-api:

Private API
===========

.. autosummary::
   :toctree: python

   django_evolution.diff
   django_evolution.mock_models
   django_evolution.mutators
   django_evolution.support
   django_evolution.compat.apps
   django_evolution.compat.commands
   django_evolution.compat.datastructures
   django_evolution.compat.db
   django_evolution.compat.models
   django_evolution.compat.picklers
   django_evolution.compat.py23
   django_evolution.db.common
   django_evolution.db.mysql
   django_evolution.db.postgresql
   django_evolution.db.sql_result
   django_evolution.db.sqlite3
   django_evolution.db.state
   django_evolution.utils.apps
   django_evolution.utils.datastructures
   django_evolution.utils.evolutions
   django_evolution.utils.graph
   django_evolution.utils.migrations
   django_evolution.utils.models
   django_evolution.utils.sql

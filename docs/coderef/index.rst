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
   django_evolution.conf
   django_evolution.consts
   django_evolution.deprecation
   django_evolution.errors
   django_evolution.evolve
   django_evolution.evolve.base
   django_evolution.evolve.evolver
   django_evolution.evolve.evolve_app_task
   django_evolution.evolve.purge_app_task
   django_evolution.models
   django_evolution.mutations
   django_evolution.mutations.add_field
   django_evolution.mutations.base
   django_evolution.mutations.change_field
   django_evolution.mutations.change_meta
   django_evolution.mutations.delete_application
   django_evolution.mutations.delete_field
   django_evolution.mutations.delete_model
   django_evolution.mutations.move_to_django_migrations
   django_evolution.mutations.rename_app_label
   django_evolution.mutations.rename_field
   django_evolution.mutations.rename_model
   django_evolution.mutations.sql_mutation
   django_evolution.serialization
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
   django_evolution.mutators.app_mutator
   django_evolution.mutators.model_mutator
   django_evolution.mutators.sql_mutator
   django_evolution.placeholders
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

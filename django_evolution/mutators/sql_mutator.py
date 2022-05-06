"""Mutator that applies arbitrary SQL to the database.

Version Added:
    2.2
"""

from __future__ import unicode_literals


class SQLMutator(object):
    """A mutator that applies arbitrary SQL to the database.

    This is instantiated by :py:class:`~django_evolution.mutators.app_mutator.
    AppMutator`, and should not be created manually.

    Version Changed:
        2.2:
        Moved into the :py:mod:`django_evolution.mutators.sql_mutator` module.
    """

    def __init__(self, mutation, sql):
        self.mutation = mutation
        self.sql = sql

    def to_sql(self):
        return self.sql

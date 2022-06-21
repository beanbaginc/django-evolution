"""Mutator that applies arbitrary SQL to the database.

Version Added:
    2.2
"""

from __future__ import unicode_literals

from django_evolution.mutators.base import BaseMutator


class SQLMutator(BaseMutator):
    """A mutator that applies arbitrary SQL to the database.

    This is instantiated by :py:class:`~django_evolution.mutators.app_mutator.
    AppMutator`, and should not be created manually.

    Version Changed:
        2.2:
        Moved into the :py:mod:`django_evolution.mutators.sql_mutator` module.
    """

    def __init__(self, mutation, sql):
        """Initialize the mutator.

        Args:
            mutation (django_evolution.mutations.base.BaseMutation):
                The mutation that generated this SQL.

            sql (list):
                The list of SQL statements. See the return type in
                :py:meth:`to_sql` for possible values.
        """
        super(SQLMutator, self).__init__()

        self.mutation = mutation
        self.sql = sql

    def to_sql(self):
        """Return SQL passed to this mutator.

        Returns:
            list:
            The list of SQL statements.

            Each item may be one of the following:

            1. A Unicode string representing an SQL statement
            2. A tuple in the form of ``(sql_statement, sql_params)``
            3. An instance of :py:class:`django_evolution.db.sql_result.
               SQLResult`.
        """
        self.finalize()

        return self.sql

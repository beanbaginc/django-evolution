"""Utilities for working with SQL statements."""

from __future__ import print_function, unicode_literals

from django.db import connections

from django_evolution.compat import six
from django_evolution.compat.db import atomic
from django_evolution.db import EvolutionOperationsMulti


class SQLExecutor(object):
    """Management for the execution of SQL.

    This allows callers to perform raw SQL queries against the database,
    and to do so with a fine degree of transaction management. Callers can
    continually add new SQL to execute and, in-between, enter into a new
    transaction, ensure a previous transaction is already open, or close out
    any existing transaction.

    Through this, it can effectively script a set of transactions and queries
    in a more loose form than normally allowed by Django.

    Version Added:
        2.1
    """

    def __init__(self, database, check_constraints=True):
        """Initialize the executor.

        Args:
            database (unicode):
                The registered database name where queries will be executed.

            check_constraints (bool, optional):
                Whether to check constraints during the execution of SQL.
                If disabled, it's up to the caller to manually invoke a
                constraint check.
        """
        self._check_constraints = check_constraints
        self._connection = connections[database]
        self._database = database

        self._constraints_disabled = False
        self._cursor = None
        self._evolver_backend = None
        self._latest_transaction = None

    def __enter__(self):
        """Enter the context manager.

        This will prepare internal state for execution, and optionally disable
        constraint checking (if requested during construction).

        The context manager must be entered before operations will work.

        Context:
            SQLExecutor:
            This instance.
        """
        connection = self._connection
        database = self._database

        if not self._check_constraints:
            self._constraints_disabled = \
                connection.disable_constraint_checking()

        self._cursor = connection.cursor()
        self._evolver_backend = \
            EvolutionOperationsMulti(database).get_evolver()

        return self

    def __exit__(self, *args, **kwargs):
        """Exit the context manager.

        This will commit any transaction that may be in progress, close the
        database cursor, and re-enable constraint checking if it were
        previously disabled.

        Args:
            *args (tuple, unused):
                Unused positional arguments.

            **kwargs (dict, unused):
                Unused keyword arguments.
        """
        self.finish_transaction()

        self._cursor.close()
        self._cursor = None

        if self._constraints_disabled:
            self._connection.enable_constraint_checking()

    def new_transaction(self):
        """Start a new transaction.

        This will commit any prior transaction, if one exists, and then start
        a new one.
        """
        self.finish_transaction()

        transaction = atomic()
        transaction.__enter__()
        self._latest_transaction = transaction

    def ensure_transaction(self):
        """Ensure a transaction has started.

        If no existing transaction has started, this will start a new one.
        """
        if not self._latest_transaction:
            self.new_transaction()

    def finish_transaction(self):
        """Finish and commit a transaction."""
        transaction = self._latest_transaction

        if transaction:
            transaction.__exit__(None, None, None)
            self._latest_transaction = None

    def run_sql(self, sql, capture=False, execute=False):
        """Run (execute and/or capture) a list of SQL statements.

        Args:
            sql (list):
                A list of SQL statements. Each entry might be a string, a
                tuple consisting of a format string and formatting arguments,
                or a subclass of :py:class:`BaseGroupedSQL`, or a callable
                that returns a list of the above.

            capture (bool, optional):
                Whether to capture any processed SQL statements.

            execute (bool, optional):
                Whether to execute any executed SQL statements and return them.

        Returns:
            list of unicode:
            The list of SQL statements executed, if passing
            ``capture_sql=True``. Otherwise, this will just be an empty list.
        """
        qp = self._evolver_backend.quote_sql_param
        cursor = self._cursor

        statement = None
        params = None
        out_sql = []

        try:
            self.ensure_transaction()

            for statement, params in self._prepare_sql(sql):
                if capture:
                    if params:
                        out_sql.append(statement % tuple(
                            qp(param)
                            for param in params
                        ))
                    else:
                        out_sql.append(statement)

                if execute:
                    cursor.execute(statement, params)
        except Exception as e:
            # Augment the exception so that callers can get the SQL statement
            # that failed.
            e.last_sql_statement = (statement, params)

            raise

        return out_sql

    def _prepare_sql(self, sql):
        """Prepare batches of SQL statements for execution.

        This will take the SQL statements that have been scheduled to be run
        and yields them one-by-one for execution.

        Each entry in ``sql`` may be a single statement, a list of statements,
        or a function that takes a cursor and returns a statement/list of
        statements.

        Each statement can be either a string or a tuple consisting of the
        statement and parameters to pass to it.

        All comments and blank lines will be filtered out.

        Args:
            sql (object):
                The list of statements to prepare for execution. Each entry
                might be a string, a tuple consisting of a format string and
                formatting arguments, or a callable that returns a list of the
                above.

        Yields:
            tuple:
            A tuple containing a statement to execute, in order. This will be
            a tuple containing:

            1. The SQL statement as a string
            2. A tuple of parameters for the SQL statements (which may be
               empty)
        """
        normalize_value = self._evolver_backend.normalize_value

        for statements in sql:
            if callable(statements):
                statements = statements(self._cursor)

            if not isinstance(statements, list):
                statements = [statements]

            for statement in statements:
                if isinstance(statement, tuple):
                    statement, params = statement
                    assert isinstance(params, tuple)
                else:
                    params = None

                assert isinstance(statement, six.text_type)

                statement = statement.strip()

                if statement and not statement.startswith('--'):
                    if params is not None:
                        params = tuple(
                            normalize_value(param)
                            for param in params
                        )

                    yield statement, params

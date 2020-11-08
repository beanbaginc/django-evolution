"""Utilities for working with SQL statements."""

from __future__ import print_function, unicode_literals

import logging

from django.db import connections
from django.db.transaction import TransactionManagementError

from django_evolution.compat import six
from django_evolution.compat.db import atomic
from django_evolution.db import EvolutionOperationsMulti


logger = logging.getLogger(__name__)


class BaseGroupedSQL(object):
    """Base class for a grouped list of SQL statements.

    This is a simple wrapper around a list of SQL statements, used to
    group statements under some category defined by a subclass.

    Attributes:
        sql (list):
            A list of SQL statements, as allowed by :py:func:`run_sql`.
    """

    def __init__(self, sql):
        """Initialize the group.

        Args:
            sql (list):
                A list of SQL statements, as allowed by :py:func:`run_sql`.
        """
        self.sql = sql


class NewTransactionSQL(BaseGroupedSQL):
    """A list of SQL statements to execute in its own transaction."""


class NoTransactionSQL(BaseGroupedSQL):
    """A list of SQL statements to execute outside of a transaction."""


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

        if (connection.in_atomic_block and
            not connection.features.can_rollback_ddl):
            logger.warning('Some database schema modifications may not be '
                           'able to be rolled back on this database if '
                           'something goes wrong.')

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

        Raises:
            django.db.transaction.TransactionManagementError:
                Could not execute a batch of SQL statements inside of an
                existing transaction.
        """
        qp = self._evolver_backend.quote_sql_param
        cursor = self._cursor

        statement = None
        params = None
        out_sql = []

        try:
            batches = self._prepare_transaction_batches(
                self._prepare_sql(sql))

            if execute and self._connection.in_atomic_block:
                # Check if there are any statements that must run outside of
                # a transaction.
                batches = list(batches)

                for batch, use_transaction in batches:
                    if not use_transaction:
                        logging.error(
                            'Unable to execute the following SQL inside of a '
                            'transaction: %r',
                            batch)

                        raise TransactionManagementError(
                            'Unable to execute SQL inside of an existing '
                            'transaction. See the logging for more '
                            'information.')

            for i, (batch, use_transaction) in enumerate(batches):
                if execute:
                    if use_transaction:
                        self.new_transaction()
                    else:
                        self.finish_transaction()

                if capture and i > 0:
                    if use_transaction:
                        out_sql.append('-- Start of a new transaction:')
                    else:
                        out_sql.append('-- Run outside of a transaction:')

                for statement, params in batch:
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

        All comments and blank lines will be filtered out.

        Args:
            sql (object):
                A list of SQL statements. Each entry might be a string, a
                tuple consisting of a format string and formatting arguments,
                or a subclass of :py:class:`BaseGroupedSQL`, or a callable
                that returns a list of the above.

        Yields:
            tuple:
            A tuple containing a statement to execute, in order. This will be
            a tuple containing:

            1. The SQL statement as a string
            2. A tuple of parameters for the SQL statements (which may be
               empty)
            3. Whether this statement should be run in a transaction.
            4. Whether this statement's transaction should be the start of a
               brand new, independent transaction (rather than using a
               previous one).
        """
        normalize_value = self._evolver_backend.normalize_value

        for statements in sql:
            if callable(statements):
                statements = statements(self._cursor)

                for result in self._prepare_sql(statements):
                    yield result
            else:
                new_transaction = False

                if isinstance(statements, NoTransactionSQL):
                    use_transaction = False
                    statements = statements.sql
                elif isinstance(statements, NewTransactionSQL):
                    new_transaction = True
                    use_transaction = True
                    statements = statements.sql
                else:
                    use_transaction = True

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

                        yield (statement, params, use_transaction,
                               new_transaction)

                        # If we've set this above, reset it. We only want the
                        # first statement in a batch to flag a new transaction.
                        new_transaction = False

    def _prepare_transaction_batches(self, prepared_sql):
        """Prepare batches of SQL statements to run together.

        This takes in prepared SQL statements and generates batches of
        statements to run together inside or outside of a transaction.

        Args:
            prepared_sql (list of tuple):
                A list of SQL statement information generated by
                :py:meth:`_prepare_sql`.

        Yields:
            tuple:
            Information on a batch of statements to to execute. This will be
            a tuple containing:

            1. The list of SQL statements.
            2. Whether to execute these statements in a transaction.
        """
        batch = None
        last_use_transaction = None

        for (statement, params, use_transaction,
             new_transaction) in prepared_sql:
            if new_transaction or use_transaction is not last_use_transaction:
                if batch:
                    yield batch, last_use_transaction

                batch = []
                last_use_transaction = use_transaction

            batch.append((statement, params))

        if batch:
            yield batch, last_use_transaction

"""Utilities for working with SQL statements."""

from __future__ import print_function, unicode_literals

from django.db import connections

from django_evolution.compat import six
from django_evolution.db import EvolutionOperationsMulti


def write_sql(sql, database):
    """Output and return a list of SQL statements.

    Args:
        sql (list):
            A list of SQL statements. Each entry might be a string, or a
            tuple consisting of a format string and formatting arguments.

        database (unicode):
            The database the SQL statements would be executed on.

    Returns:
        list of unicode:
        The formatted list of SQL statements.
    """
    cursor = connections[database].cursor()

    try:
        return run_sql(cursor=cursor,
                       sql=sql,
                       database=database,
                       execute=False,
                       capture=True)
    finally:
        cursor.close()


def execute_sql(cursor, sql, database, capture=False):
    """Execute a list of SQL statements.

    Args:
        cursor (object):
            The database backend's cursor.

        sql (list):
            A list of SQL statements. Each entry might be a string, or a
            tuple consisting of a format string and formatting arguments.

        database (unicode):
            The database the SQL statements would be executed on.

        capture (bool, optional):
            Whether to capture any processed SQL statements.
    """
    return run_sql(cursor=cursor,
                   sql=sql,
                   database=database,
                   execute=True,
                   capture=capture)


def run_sql(sql, cursor, database, capture=False, execute=False):
    """Run (execute and/or capture) a list of SQL statements.

    Args:
        cursor (object):
            The database backend's cursor.

        sql (list):
            A list of SQL statements. Each entry might be a string, or a
            tuple consisting of a format string and formatting arguments.

        database (unicode):
            The database the SQL statements would be executed on.

        capture (bool, optional):
            Whether to capture any processed SQL statements.

        execute (bool, optional):
            Whether to execute any executed SQL statements and return them.

    Returns:
        list of unicode:
        The list of SQL statements executed, if passing ``capture_sql=True``.
        Otherwise, this will just be an empty list.
    """
    evolver = EvolutionOperationsMulti(database).get_evolver()
    qp = evolver.quote_sql_param

    statement = None
    params = None
    out_sql = []

    try:
        for statement, params in _prepare_sql(evolver, sql, cursor):
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


def _prepare_sql(evolver, sql, cursor):
    """Prepare batches of SQL statements for execution.

    This will take the SQL statements that have been scheduled to be run and
    yields them one-by-one for execution.

    Each entry in ``sql`` may be a single statement, a list of statements, or
    a function that takes a cursor and returns a statement/list of statements.

    Each statement can be either a string or a tuple consisting of the
    statement and parameters to pass to it.

    All comments and blank lines will be filtered out.

    Args:
        sql (object):
            The list of statements to prepare for execution.

        cursor (object):
            The database backend's cursor.

    Yields:
        tuple:
        A tuple containing a statement to execute, in order. This will be a
        tuple containing:

        1. The SQL statement as a string
        2. A tuple of parameters for the SQL statements (which may be empty)
    """
    for statements in sql:
        if callable(statements):
            statements = statements(cursor)

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
                        evolver.normalize_value(param)
                        for param in params
                    )

                yield statement, params

"""Utilities for working with SQL statements."""

from __future__ import print_function, unicode_literals

from django.utils import six

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
    evolver = EvolutionOperationsMulti(database).get_evolver()
    qp = evolver.quote_sql_param
    out_sql = []

    for statement in sql:
        if isinstance(statement, tuple):
            statement = six.text_type(statement[0] % tuple(
                qp(evolver.normalize_value(s))
                for s in statement[1]
            ))

        print(statement)
        out_sql.append(statement)

    return out_sql


def execute_sql(cursor, sql, database):
    """Execute a list of SQL statements.

    Args:
        cursor (object):
            The database backend's cursor.

        sql (list):
            A list of SQL statements. Each entry might be a string, or a
            tuple consisting of a format string and formatting arguments.

        database (unicode):
            The database the SQL statements would be executed on.
    """
    evolver = EvolutionOperationsMulti(database).get_evolver()
    statement = None

    try:
        for statement in sql:
            if isinstance(statement, tuple):
                statement = (statement[0].strip(), statement[1])

                if statement[0] and not statement[0].startswith('--'):
                    cursor.execute(statement[0], tuple(
                        evolver.normalize_value(s)
                        for s in statement[1]
                    ))
            else:
                statement = statement.strip()

                if statement and not statement.startswith('--'):
                    cursor.execute(statement)
    except Exception as e:
        # Augment the exception so that callers can get the SQL statement
        # that failed.
        e.last_sql_statement = statement

        raise

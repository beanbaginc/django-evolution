from django_evolution.db import EvolutionOperationsMulti


def write_sql(sql, database):
    "Output a list of SQL statements, unrolling parameters as required"
    evolver = EvolutionOperationsMulti(database).get_evolver()
    qp = evolver.quote_sql_param

    for statement in sql:
        if isinstance(statement, tuple):
            print unicode(statement[0] % tuple(
                qp(evolver.normalize_value(s))
                for s in statement[1]
            ))
        else:
            print unicode(statement)


def execute_sql(cursor, sql):
    """
    Execute a list of SQL statements on the provided cursor, unrolling
    parameters as required
    """
    evolver = EvolutionOperationsMulti('default').get_evolver()

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

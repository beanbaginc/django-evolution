from django_evolution.mutations import get_evolution_module

# Import the quote_sql_param function from the database backend.
quote_sql_param = get_evolution_module().quote_sql_param

def write_sql(sql):
    "Output a list of SQL statements, unrolling parameters as required"
    for statement in sql:
        if isinstance(statement, tuple):
            print unicode(statement[0] % tuple(quote_sql_param(s) for s in statement[1]))
        else:
            print unicode(statement)

def execute_sql(cursor, sql):
    """
    Execute a list of SQL statements on the provided cursor, unrolling 
    parameters as required
    """
    for statement in sql:
        if isinstance(statement, tuple):
            if not statement[0].startswith('--'):
                cursor.execute(*statement)
        else:
            if not statement.startswith('--'):
                cursor.execute(statement)  

from django.core.management.color import no_style
from django.core.management.sql import sql_create, sql_delete
from django.db.backends.util import truncate_name
from django.db import connection, transaction

from django_evolution import signature
from django_evolution.tests import models as evo_test

def test_proj_sig(model, app_label='testapp', model_name='TestModel', version=1):
    "Generate a dummy project signature based around a single model"
    return {
        app_label: {
            model_name: signature.create_model_sig(model),
        }, 
        '__version__': version,
    }
    
def execute_sql(sql, output=False):
    "A transaction wrapper for executing a list of SQL statements"
    try:
        # Begin Transaction
        transaction.enter_transaction_management()
        transaction.managed(True)
        cursor = connection.cursor()
        
        # Perform the SQL
        for statement in sql:
            if output:
                print statement
            cursor.execute(statement)  
        transaction.commit()
        transaction.leave_transaction_management()
    except Exception, ex:
        transaction.rollback()
        raise ex

def execute_test_sql(sql, cleanup=None, debug=False):
    """
    Execute a test SQL sequence. This method also creates and destroys the models
    that have been registered against the test module.
    
    cleanup is a list of extra sql statements required to clean up. This is
    primarily for any extra m2m tables that were added during a test that won't 
    be cleaned up by Django's sql_delete() implementation.
    
    debug is a helper flag. It displays the ALL the SQL that would be executed,
    (including setup and teardown SQL), and executes the Django-derived setup/teardown
    SQL.
    """
    style = no_style()
    execute_sql(sql_create(evo_test, style), output=debug)
    if debug:
        for statement in sql:
            print statement
    else:
        execute_sql(sql, output=True)
    if cleanup:
        if debug:
            for statement in sql:
                print statement
        else:
            execute_sql(cleanup, output=debug)
    execute_sql(sql_delete(evo_test, style), output=debug)

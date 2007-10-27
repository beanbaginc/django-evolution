from django.core.management.color import no_style
from django.core.management.sql import sql_create, sql_delete
from django.db.backends.util import truncate_name
from django.db import connection, transaction

from django_evolution.management import signature
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

def execute_test_sql(sql):
    """
    Execute a test SQL sequence. This method also creates and destroys the models
    that have been registered against the test module.
    """
    style = no_style()
    execute_sql(sql_create(evo_test, style))    
    execute_sql(sql, output=True)
    execute_sql(sql_delete(evo_test, style))

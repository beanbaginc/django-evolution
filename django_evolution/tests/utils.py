from django.core.management.color import no_style
from django.core.management.sql import sql_create, sql_delete, sql_indexes
from django.db import connection, transaction, settings, models
from django.db.backends.util import truncate_name
from django.db.models.loading import cache

from django_evolution import signature
from django_evolution.tests import models as evo_test
from django_evolution.utils import write_sql, execute_sql

DEFAULT_TEST_ATTRIBUTE_VALUES = {
    models.CharField: 'TestCharField',
    models.IntegerField: '123',
    models.AutoField: None,
}

def test_proj_sig(*models, **kwargs):
    "Generate a dummy project signature based around a single model"
    app_label = kwargs.get('app_label','django_evolution')
    version = kwargs.get('version',1)
    proj_sig = {
        app_label: {
        }, 
        '__version__': version,
    }
    
    for name,model in models:
        proj_sig[app_label][name] = signature.create_model_sig(model)
    
        # Insert a fake entry into the model cache
        cache.app_models[app_label][name.lower()] = model
        
    return proj_sig
    
def execute_transaction(sql, output=False):
    "A transaction wrapper for executing a list of SQL statements"
    try:
        # Begin Transaction
        transaction.enter_transaction_management()
        transaction.managed(True)
        cursor = connection.cursor()
        
        # Perform the SQL
        if output:
            write_sql(sql)
        execute_sql(cursor, sql)
        
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
    execute_transaction(sql_create(evo_test, style), output=debug)
    execute_transaction(sql_indexes(evo_test, style), output=debug)
    create_test_data(models.get_models(evo_test))
    
    if debug:
        write_sql(sql)
    else:
        execute_transaction(sql, output=True)
    if cleanup:
        if debug:
            write_sql(cleanup)
        else:
            execute_transaction(cleanup, output=debug)
    execute_transaction(sql_delete(evo_test, style), output=debug)
    
def create_test_data(app_models):
    deferred_models = []
    deferred_fields = {}
    for model in app_models:
        params = {}
        deferred = False
        for field in model._meta.fields:
            if not deferred:
                if type(field) == models.ForeignKey or type(field) == models.ManyToManyField:
                    related_model = field.rel.to
                    if related_model.objects.count():
                        related_instance = related_model.objects.all()[0]
                    else:
                        if field.null == False:
                            # Field cannot be null yet the related object hasn't been created yet
                            # Defer the creation of this model
                            deferred = True
                            deferred_models.append(model)
                        else:
                            # Field cannot be set yet but null is acceptable for the moment
                            deferred_fields[type(model)] = deferred_fields.get(type(model), []).append(field)
                            related_instance = None
                    if not deferred:
                        if type(field) == models.ForeignKey:
                            params[field.name] = related_instance
                        else:
                            params[field.name] = [related_instance]
                else:
                    params[field.name] = DEFAULT_TEST_ATTRIBUTE_VALUES[type(field)]

        if not deferred:
            model(**params).save()
    
    # Create all deferred models.
    if deferred_models:
        create_test_data(deferred_models)
        
    # All models should be created (Not all deferred fields have been populated yet)
    # Populate deferred fields that we know about.
    # Here lies untested code!
    if deferred_fields:
        for model, field_list in deferred_fields.items():
            for field in field_list:
                related_model = field.rel.to
                related_instance = related_model.objects.all()[0]
                if type(field) == models.ForeignKey:
                    setattr(model, field.name, related_instance) 
                else:
                    getattr(model, field.name).add(related_instance)
            model.save()
    
def test_sql_mapping(test_field_name):
    engine = settings.DATABASE_ENGINE
    sql_for_engine = __import__('django_evolution.tests.db.%s' % (settings.DATABASE_ENGINE), {}, {}, [''])
    return getattr(sql_for_engine, test_field_name)

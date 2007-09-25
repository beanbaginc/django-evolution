"""
Performs schema evolution.
"""

from django.dispatch import dispatcher
from django.db.models.base import Model, ModelBase
from django.db.models import get_apps, get_models, signals
from django.contrib.evolution.models import *
from django.db import transaction, connection
from django.db.models.fields.related import *

from os import path
import copy

def hint(app_name, migration_name):
    try:
        import cPickle as pickle
    except ImportError:
        import pickle as pickle

    #app_name = '.'.join(app.__name__.split('.')[:-1])
    evolution_module = __import__(app_name + '.evolutions',{},{},[''])
    last_evolution = Evolution.objects.filter(app_name=app_name)
    last_evolution = last_evolution.order_by('version')
    if last_evolution.count() > 0:
        last_evolution = last_evolution[0]
        last_evolution_dict = pickle.loads(str(last_evolution.snapshot))
        try:
            module_name = [evolution_module.__name__,migration_name]
            migration_module = __import__('.'.join(module_name),{},{},[''])
            directory_name = path.dirname(evolution_module.__file__)
            sqlfile = path.join(directory_name,migration_name)+path.extsep+'sql'
            handle = open(sqlfile,'w')
            for mutation in migration_module.MUTATIONS:
                # Collect and write the sql statements to file
                mutation.pre_mutate(last_evolution_dict)
                for statement in mutation.mutate(last_evolution_dict):
                    handle.write(statement+'\n')
                mutation.post_mutate()
            handle.flush()
            handle.close()
            
        except ImportError:
            print 'Error: Cannot find the python migration named', migration_name
    else:
        print 'Please run syncdb with evolutions enabled before modifying your models and running evolutions hint.'
    
def evolution(app, created_models):
    """
    Determine if an evolution is necessary and apply it if necessary.
    """
    try:
        import cPickle as pickle
    except ImportError:
        import pickle as pickle

    app_name = '.'.join(app.__name__.split('.')[:-1])
    application_label,model_dict = create_model_dict(app)
    snapshot = pickle.dumps(model_dict)
    
    last_evolution = Evolution.objects.filter(app_name=app_name)
    last_evolution = last_evolution.order_by('version')
    if last_evolution.count() > 0:
        last_evolution = last_evolution[0]
        if not last_evolution.snapshot == snapshot:
            # Migration Required. Evolve the model.
            print 'Migration Required - %s'%application_label
            last_evolution_dict = pickle.loads(str(last_evolution.snapshot))
            class_name = app_name + '.evolutions.evolution'
            evolution_module = __import__(app_name + '.evolutions',{},{},[''])
            evolution_success = evolve_model(evolution_module, 
                                             last_evolution.version, 
                                             last_evolution_dict,
                                             model_dict)
            if evolution_success:
                evolution = Evolution(app_name=app_name,version=0,snapshot=snapshot)
                evolution.save()
                print 'Evolution Successful - %s'%application_label
            else:
                # otherwise something went wrong during the evolution process
                print 'Evolution Failure - %s'%application_label
    else:
        # This is the first time that this application has been seen
        # We need to create a new entry.
        evolution = Evolution(app_name=app_name,version=0,snapshot=snapshot)
        evolution.save()
        
def evolve_model(evolution_module, current_version, current_model_dict, target_model_dict):
    """
    Evolves the model from the current state to the new state via a series
    of mutations.
    """
    # For each item in the evolution sequence. Check each item to see if it is
    # a python file or an sql file.
    sql_statements = []         # The list of sql statements to execute
    perform_simulation = True
    simulation_version = copy.deepcopy(current_model_dict)
    
    directory_name = path.dirname(evolution_module.__file__)
    for version in range(current_version,len(evolution_module.SEQUENCE),1):
        migration_name = evolution_module.SEQUENCE[version]
        sql_file = path.join(directory_name, migration_name+'.sql')
        if path.exists(sql_file):
            perform_simulation = False
            temp = []
            sql_fh = open(sql_file)
            for line in sql_fh:
                temp.append(line)
            sql_statements.append(''.join(temp))
        else:
            try:
                module_name = [evolution_module.__name__,migration_name]
                migration_module = __import__('.'.join(module_name),{},{},['']);
                for mutation in migration_module.MUTATIONS:
                    # Continue to perform simulations until such time we 
                    # discover that it is no longer possible (raw sql is used).
                    if perform_simulation:                    
                        mutation.pre_simulate()
                        mutation.simulate(simulation_version)
                        mutation.post_simulate()
                    
                    # Collect the SQL statements
                    mutation.pre_mutate(current_model_dict)
                    sql_statements.extend(mutation.mutate(current_model_dict))
                    mutation.post_mutate()
                
            except ImportError, ie:
                print 'Error: Failed to find an SQL or Python file named', migration_name
                return False    

    if perform_simulation: 
        if simulation_version == target_model_dict:
            return execute_sql(sql_statements)
        else:
            # Simulation Failure
            print 'Simulation Failure'
            show_differences(simulation_version, target_model_dict)
            return False
    else:
        return execute_sql(sql_statements)

def execute_sql(sql_statements):
    try:
        # Begin Transaction
        transaction.enter_transaction_management()
        transaction.managed(True)
        cursor = connection.cursor()
        for statement in sql_statements:
            cursor.execute(statement)  
        transaction.commit()
        success = True
    except Exception, ex:
        print 'Exception. Rolling back.'
        print ex
        transaction.rollback()
        success = False
        
    return success
    
def show_differences(dict_a, dict_b):
    """
    Shows the differences between two representations of the model as a dict.
    """
    # This is mainly for debugging purposes 
    for key_a, value_a in dict_a.items():
        try:
            value_b = dict_b[key_a]
            if not value_a == value_b:
                if isinstance(value_a, dict) and isinstance(value_b, dict):
                    show_differences(value_a, value_b)
                else:
                    print 'Values do not match:'
                    print 'Key: %s\t Value:%s'%(str(key_a), str(value_a))
                    print 'Key: %s\t Value:%s'%(str(key_a), str(value_b))
                    
        except KeyError, ke:
            print 'Dictionary is missing key: %s'%key_a
            
def create_model_dict(app):
    """
    Creates a dictionary representation of the application models.
    """
    db_attributes = ['core',
                     'maxlength',
                     'max_digits',  #?          
                     'decimal_places', #?
                     'null',
                     'blank',
                     'db_column',
                     'db_index',
                     'db_tablespace',
                     'primary_key',
                     'unique',
                     ]
    model_dict = {}
    application_label = None
    for attribute_str in dir(app):
        attribute = getattr(app, attribute_str)
        if isinstance(attribute, ModelBase):
            try:
                field_dict = model_dict[attribute_str]
            except KeyError:
                field_dict = {}
                model_dict[attribute_str] = field_dict
            if not application_label:
                application_label = attribute._meta.app_label
            field_dict['unique_together'] = attribute._meta.unique_together
            field_dict['db_columns'] = [field.column for field in attribute._meta.fields]

            field_list = attribute._meta.fields[:]
            field_list.extend(attribute._meta.many_to_many)
            for field in field_list:
                attribute_dict = {}
                field_dict[field.name] = attribute_dict
                attribute_dict['internal_type'] = field.get_internal_type()
                if isinstance(field, ManyToManyField):
                    attribute_dict['m2m_db_table'] = field.m2m_db_table()
                else:
                    attribute_dict['column'] = field.column
                for attrib in db_attributes:
                    if hasattr(field,attrib):
                        attribute_dict[attrib] = getattr(field,attrib)
    return (application_label,model_dict)
dispatcher.connect(evolution, signal=signals.post_syncdb)


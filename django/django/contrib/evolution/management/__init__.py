"""
Performs schema evolution.
"""

from django.dispatch import dispatcher
from django.db.models.base import Model, ModelBase
from django.db.models import get_apps, get_models, signals
from django.contrib.evolution.models import *
from django.db import transaction, connection
from django.db.models import loading
from django.db.models.fields.related import *
from django.contrib.evolution import EvolutionException

from os import path
import pprint
import copy
try:
    import cPickle as pickle
except ImportError:
    import pickle as pickle

def hint(app_name, migration_name):
    evolution_module = __import__(app_name + '.evolutions',{},{},[''])
    directory_name = path.dirname(evolution_module.__file__)
    sqlfile = path.join(directory_name,migration_name)+path.extsep+'sql'
    sql_statements = sql_hint(app_name, migration_name)

    handle = open(sqlfile,'w')
    handle.write('\n'.join(sql_statements))
    handle.flush()
    handle.close()
        
def sql_hint(app_name, migration_name):
    """
    Returns the list of sql statements that would be executed for the application to be migrated to the specified migration_name.
    """
    try:
        evolution_module = __import__(app_name + '.evolutions',{},{},[''])
    except ImportError:
        raise EvolutionException('Error: Cannot find the evolutions directory at %s.evolutions'%app_name)
    try:
        from_version = evolution_module.SEQUENCE.index(migration_name)
        
    except ValueError:
        params = (migration_name,', '.join(evolution_module.SEQUENCE))
        raise EvolutionException('Error: Cannot find the migration named %s. The allowable choices are %s.'%params)
    target_version = from_version + 1
    try:
        last_evolution = Evolution.objects.get(app_name=app_name, version=from_version)
        last_evolution_dict = pickle.loads(str(last_evolution.signature))
    except Evolution.DoesNotExist:
        raise EvolutionException('Please run syncdb with evolutions enabled before modifying your models and running evolutions hint.')
    try:
        target_evolution = Evolution.objects.get(app_name=app_name, version=target_version)
        target_evolution_dict = pickle.loads(str(target_evolution.signature))
    except Evolution.DoesNotExist:
        # This can be caused if the migration being hinted is the last one on the list
        app_label = app_name.split('.')
        app_label = app_label[len(app_label)-1]
        application_label,target_evolution_dict = create_model_dict(loading.get_app(app_label))

    return get_sql(evolution_module, 
                   from_version, 
                   target_version, 
                   last_evolution_dict, 
                   target_evolution_dict)
    
def evolution(app, created_models):
    """
    Determine if an evolution is necessary and apply it if necessary.
    """
    app_name = '.'.join(app.__name__.split('.')[:-1])
    application_label,model_dict = create_model_dict(app)
    signature = pickle.dumps(model_dict)
    
    last_evolution = Evolution.objects.filter(app_name=app_name)
    last_evolution = last_evolution.order_by('version')
    if last_evolution.count() > 0:
        last_evolution = last_evolution[0]
        if not last_evolution.signature == signature:
            # Migration Required. Evolve the model.
            print 'Migration Required - %s'%application_label
            last_evolution_dict = pickle.loads(str(last_evolution.signature))
            class_name = app_name + '.evolutions.evolution'
            evolution_module = __import__(app_name + '.evolutions',{},{},[''])
            sql = get_sql(evolution_module, 
                          last_evolution.version, 
                          len(evolution_module.SEQUENCE), 
                          last_evolution_dict, 
                          model_dict)
            for s in sql:
                print s
            execute_sql(sql)
            print 'Evolution Successful'
        else:
            print 'Evolution not required - %s'%application_label
    else:
        # This is the first time that this application has been seen
        # We need to create a new entry.

        # In general there will be an application label and model_dict to save. The
        # exception to the rule is for empty models (such as in the django tests).
        if application_label and model_dict:
            evolution = Evolution(app_name=app_name,version=0,signature=signature)
            evolution.save()
        
def get_sql(evolution_module, from_version, target_version, current_model_dict, target_model_dict):
    # For each item in the evolution sequence. Check each item to see if it is
    # a python file or an sql file.
    if from_version < 0:
        raise EvolutionException('Cannot evolve from a version less than zero.')
    elif target_version > len(evolution_module.SEQUENCE):
        params = (target_version,len(evolution_module.SEQUENCE))
        raise EvolutionException('Migration version %d is larger than the number of migrations in SEQUENCE (%d).'%params)

    sql_statements = []         # The list of sql statements to execute
    perform_simulation = True
    simulation_version = copy.deepcopy(current_model_dict)
    
    directory_name = path.dirname(evolution_module.__file__)

    for version in range(from_version,target_version,1):
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
                raise EvolutionException('Error: Failed to find an SQL or Python file named %s'%migration_name)

    if perform_simulation: 
        if simulation_version == target_model_dict:
            return sql_statements
        else:
            # Simulation Failure
            print 'Simulation Failure'
            show_differences(simulation_version, target_model_dict)
            print sql_statements
            # print pprint.PrettyPrinter(indent=4).pprint(simulation_version)
            #             print 79*'#'
            #             print pprint.PrettyPrinter(indent=4).pprint(target_model_dict)
            raise EvolutionException('Simulation Failure')
    else:
        return sql_statements

def execute_sql(sql_statements):
    try:
        # Begin Transaction
        transaction.enter_transaction_management()
        transaction.managed(True)
        cursor = connection.cursor()
        for statement in sql_statements:
            cursor.execute(statement)  
        transaction.commit()
    except Exception, ex:
        transaction.rollback()
        raise EvolutionException(str(ex))
        
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
            print dict_b.keys()
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
        if isinstance(attribute, ModelBase) and hasattr(attribute,'_meta'):
            try:
                field_dict = model_dict[attribute_str]
            except KeyError:
                field_dict = {}
                model_dict[attribute_str] = field_dict
            if not application_label:
                application_label = attribute._meta.app_label
            field_dict['unique_together'] = attribute._meta.unique_together

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


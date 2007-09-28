import os
import sys
import copy

from django.db import transaction, connection
from django.db.models import loading

from django_evolution import EvolutionException
from django_evolution.management.signature import compare_app_dicts

def hint(app_name, migration_name):
    evolution_module = __import__(app_name + '.evolutions',{},{},[''])
    directory_name = os.path.dirname(evolution_module.__file__)
    sqlfile = os.path.join(directory_name,migration_name) + os.path.extsep + 'sql'
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
        application_label,target_evolution_dict = create_app_dict(loading.get_app(app_label))

    return get_sql(evolution_module, 
                   from_version, 
                   target_version, 
                   last_evolution_dict, 
                   target_evolution_dict)
                   
def get_sql(evolution_module, from_version, target_version, current_app_dict, target_app_dict):
    # For each item in the evolution sequence. Check each item to see if it is
    # a python file or an sql file.
    if from_version < 0:
        raise EvolutionException('Cannot evolve from a version less than zero.')
    elif target_version > len(evolution_module.SEQUENCE):
        params = (target_version,len(evolution_module.SEQUENCE))
        raise EvolutionException('Migration version %d is larger than the number of migrations in SEQUENCE (%d).'%params)

    sql_statements = []         # The list of sql statements to execute
    perform_simulation = True
    simulation_version = copy.deepcopy(current_app_dict)
    
    directory_name = os.path.dirname(evolution_module.__file__)
    for version in range(from_version,target_version,1):
        migration_name = evolution_module.SEQUENCE[version]
        sql_file = os.path.join(directory_name, migration_name+'.sql')
        if os.path.exists(sql_file):
            perform_simulation = False
            temp = []
            sql_fh = open(sql_file)
            for line in sql_fh:
                temp.append(line)
            sql_statements.append(''.join(temp))
        else:
            try:
                module_name = [evolution_module.__name__,migration_name]
                migration_module = __import__('.'.join(module_name),{},{},[module_name]);
                for mutation in migration_module.MUTATIONS:
                    # Continue to perform simulations until such time we 
                    # discover that it is no longer possible (raw sql is used).
                    if perform_simulation:                    
                        mutation.pre_simulate()
                        mutation.simulate(simulation_version)
                        mutation.post_simulate()
                    
                    # Collect the SQL statements
                    mutation.pre_mutate(current_app_dict)
                    sql_statements.extend(mutation.mutate(current_app_dict))
                    mutation.post_mutate()
            except ImportError, ie:
                raise EvolutionException('Error: Failed to find an SQL or Python migration named %s' % migration_name)

    if perform_simulation: 
        if simulation_version == target_app_dict:
            return sql_statements
        else:
            # Simulation Failure
            print 'Simulation Failure'
            compare_app_dicts(simulation_version, target_app_dict)
            print sql_statements
            # print pprint.PrettyPrinter(indent=4).pprint(simulation_version)
            #             print 79*'#'
            #             print pprint.PrettyPrinter(indent=4).pprint(target_app_dict)
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
                   
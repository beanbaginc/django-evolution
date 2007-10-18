import os
import sys
import copy

from django.core.management.color import color_style
from django.db import transaction, connection
from django.db.models import loading

from django_evolution import EvolutionException, CannotSimulate, SimulationFailure
from django_evolution.management.diff import Diff
from django_evolution.mutations import SQLMutation

def get_mutations(app, from_version):
    """
    Obtain the list of mutations required to transform an application from 
    the specified version. A simulated evolution is performed to ensure
    that the resulting evolution will be successful. 
    
    If an SQL mutation is specified anywhere in the chain, the simulation
    will be aborted. However, the evolution will be allowed to continue.
    """
    # For each item in the evolution sequence. Check each item to see if it is
    # a python file or an sql file.
    app_name = '.'.join(app.__name__.split('.')[:-1])
    try:
        evolution_module = __import__(app_name + '.evolutions',{},{},[''])
        sequence = evolution_module.SEQUENCE[from_version:]
    except ImportError:
        raise EvolutionException('Cannot find evolution module for application %s' % app_name)
    except AttributeError:
        raise EvolutionException('Cannot find evolution sequence for application %s' % app_name)
    except IndexError:
        raise EvolutionException('Evolution sequence for application %s does not have enough entries' % app_name)

    mutations = []    
    directory_name = os.path.dirname(evolution_module.__file__)
    for migration_name in sequence:        
        sql_file_name = os.path.join(directory_name, migration_name+'.sql')
        if os.path.exists(sql_file_name):
            sql = []
            sql_file = open(sql_file_name)
            for line in sql_file:
                sql.append(line)
            mutations.append(SQLMutation(migration_name, sql))
        else:
            try:
                module_name = [evolution_module.__name__,migration_name]
                migration_module = __import__('.'.join(module_name),{},{},[module_name]);
                mutations.extend(migration_module.MUTATIONS)
            except ImportError, e:
                raise EvolutionException('Error: Failed to find an SQL or Python migration named %s' % migration_name)
                                
    return mutations            

def simulate_mutations(app_label, mutations, current_proj_sig, target_proj_sig):
    simulated_proj_sig = copy.deepcopy(current_proj_sig)

    for mutation in mutations:
        mutation.simulate(app_label, simulated_proj_sig)

    diff = Diff(simulated_proj_sig, target_proj_sig)
    if not diff.is_empty():
        raise SimulationFailure(diff)

def compile_mutations(app_label, mutations, current_proj_sig):
    "Convert a list of mutations into the equivalent SQL"
    sql_statements = []
    for mutation in mutations:
        sql_statements.extend(mutation.mutate(app_label, current_proj_sig))
    return sql_statements

import os
import sys
import copy

from django.core.management.color import color_style
from django.db import transaction, connection
from django.db.models import loading

from django_evolution import EvolutionException, CannotSimulate, SimulationFailure
from django_evolution.management.diff import Diff
from django_evolution.mutation import SQLMutation

def get_mutations(app, from_version, current_app_sig, target_app_sig):
    """
    Obtain the list of mutations required to transform an application from 
    the specified version. A simulated evolution is performed to ensure
    that the resulting evolution will be successful. 
    
    If an SQL mutation is specified anywhere in the chain, the simulation
    will be aborted. However, the evolution will be allowed to continue.
    """
    # For each item in the evolution sequence. Check each item to see if it is
    # a python file or an sql file.
    if from_version < 0:
        raise EvolutionException('Cannot evolve from a version less than zero.')

    app_name = '.'.join(app.__name__.split('.')[:-1])
    evolution_module = __import__(app_name + '.evolutions',{},{},[''])

    mutations = []
    
    directory_name = os.path.dirname(evolution_module.__file__)
    for migration_name in evolution_module.SEQUENCE[from_version:]:
        sql_file_name = os.path.join(directory_name, migration_name+'.sql')
        if os.path.exists(sql_file_name):
            sql = []
            sql_file = open(sql_file_name)
            for line in sql_file:
                sql.append(line)
            mutations.append(SQLMutation(sql))
        else:
            try:
                module_name = [evolution_module.__name__,migration_name]
                migration_module = __import__('.'.join(module_name),{},{},[module_name]);
                mutations.extend(migration_module.MUTATIONS)
            except:
                raise EvolutionException('Error: Failed to find an SQL or Python migration named %s' % migration_name)
                                
    return mutations            

def simulate_mutations(app, mutations, current_evolution_sig, target_app_sig):
    simulated_app_sig = copy.deepcopy(current_evolution_sig)

    for mutation in mutations:
        mutation.pre_simulate()
        mutation.simulate(simulated_app_sig)
        mutation.post_simulate()

    diff = Diff(app, simulated_app_sig, target_app_sig)
    if not diff.is_empty():
        raise SimulationFailure(diff)

def compile_mutations(mutations, current_app_sig):
    "Convert a list of mutations into the equivalent SQL"
    sql_statements = []
    for mutation in mutations:
        mutation.pre_mutate(current_app_sig)
        sql_statements.extend(mutation.mutate(current_app_sig))
        mutation.post_mutate()
    return sql_statements

from optparse import make_option
import sys
import copy
try:
    import cPickle as pickle
except ImportError:
    import pickle as pickle
    
from django.core.management.base import BaseCommand, CommandError
from django.db.models import get_apps, get_models, signals
from django.db import connection,transaction

from django_evolution import CannotSimulate, SimulationFailure
from django_evolution.models import Evolution
from django_evolution.management.signature import create_app_sig
from django_evolution.management.diff import Diff
from django_evolution.evolve import get_mutations, simulate_mutations, compile_mutations

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--verbosity', action='store', dest='verbosity', default='1',
            type='choice', choices=['0', '1', '2'],
            help='Verbosity level; 0=minimal output, 1=normal output, 2=all output'),
        make_option('--hint', action='store_true', dest='hint', default=False,
            help='Generate an evolution script that would update the app'),
        make_option('-c','--compile', action='store_true', dest='compile', default=False,
            help='Compile a Django evolution script into SQL'),
        make_option('-x','--execute', action='store_true', dest='execute', default=False,
            help='Apply the evolution to the database'),
    )
    help = 'Evolve the models in a Django project.'
    args = ''

    requires_model_validation = False

    def handle(self, *args, **options):
        verbosity = int(options['verbosity'])
        evolution_required = False
        for app in get_apps():
            app_name = '.'.join(app.__name__.split('.')[:-1])
            app_sig = create_app_sig(app)
            signature = pickle.dumps(app_sig)
        
            evolutions = Evolution.objects.filter(app_name=app_name)
            if len(evolutions) > 0:
                last_evolution = evolutions[0]
                if last_evolution.signature != signature:
                    # Migration Required. Evolve the model.
                    evolution_required = True
                    if verbosity > 1:
                        print 'Application %s requires evolution' % app_name
                    last_evolution_sig = pickle.loads(str(last_evolution.signature))
                    
                    if options['hint']:
                        diff = Diff(app, last_evolution_sig, app_sig)
                        mutations = diff.evolution()
                    else:
                        mutations = get_mutations(app, last_evolution.version, 
                                                  last_evolution_sig, app_sig)
                                                  
                    # Simulate the operation of the mutations
                    try:
                        simulate_mutations(app, mutations, last_evolution_sig, app_sig)
                    except SimulationFailure, failure:
                        print self.style.ERROR('Simulated evolution of application %s did not succeed:' % failure.diff.app_label)
                        print failure.diff
                        sys.exit(1)
                    except CannotSimulate:
                        print self.style.NOTICE('Evolution could not be simulated, possibly due to raw SQL mutations')
                    
                    # Compile the mutations into SQL
                    sql = compile_mutations(mutations, last_evolution_sig)
                    
                    if options['execute']:
                        try:
                            # Begin Transaction
                            transaction.enter_transaction_management()
                            transaction.managed(True)
                            cursor = connection.cursor()
                            for statement in sql:
                                cursor.execute(statement)  
                            transaction.commit()
                            transaction.leave_transaction_management()
                        except Exception, ex:
                            transaction.rollback()
                            print self.style.ERROR('Error during evolution of %s: %s' % (app_name, str(ex)))
                            sys.exit(1)
                            
                        # Now update the evolution table
                        if options['hint']:
                            # Hinted evolutions are stored as temporary versions
                            version = None
                        else:
                            # If not hinted, we need to find and increment the version number
                            full_evolutions = Evolution.objects.filter(app_name=app_name, 
                                                                       version__isnull=False)
                            last_full_evolution = full_evolutions[0]
                            version = last_full_evolution.version + 1 
                        new_evolution = Evolution(app_name=app_name,
                                                  version=version,
                                                  signature=signature)
                        new_evolution.save()
                    else:
                        if options['compile']:
                            print ';; Compiled evolution SQL for %s' % app_name 
                            for s in sql:
                                print s                            
                        else:
                            print '--- Evolution for %s -------------------' % app_name
                            print 'from %s import *' % app_name
                            print 
                            print 'MUTATIONS = ['
                            for m in mutations:
                                print '    ',m
                            print ']'
                else:
                    if verbosity > 1:
                        print 'Application %s is up to date' % app_name
            else:
                print self.style.ERROR("Can't evolve yet. Need to set a baseline for %s." % app_name)
                sys.exit(1)
        if evolution_required:
            if options['execute']:
                if verbosity > 0:
                    print 'Evolution successful.'
            elif not options['compile']:
                if verbosity > 0:
                    print "Trial evolution successful. Run './manage.py evolve --execute' to apply evolution."
        else:
            if verbosity > 0:
                print 'No evolution required.'

    
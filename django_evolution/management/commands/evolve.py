from optparse import make_option
import sys
try:
    import cPickle as pickle
except ImportError:
    import pickle as pickle
    
from django.core.management.base import BaseCommand, CommandError
from django.db.models import get_apps, get_models, signals
from django.db import connection,transaction

from django_evolution.models import Evolution
from django_evolution.management.signature import create_app_sig, Diff
from django_evolution.evolve import get_mutations, compile_mutations

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
        for app in get_apps():
            app_name = '.'.join(app.__name__.split('.')[:-1])
            app_sig = create_app_sig(app)
            signature = pickle.dumps(app_sig)
        
            evolutions = Evolution.objects.filter(app_name=app_name)
            if len(evolutions) > 0:
                last_evolution = evolutions[0]
                if last_evolution.signature != signature:
                    # Migration Required. Evolve the model.
                    if verbosity > 1:
                        print 'Application %s requires evolution' % app_name
                    last_evolution_sig = pickle.loads(str(last_evolution.signature))
                    
                    if options['hint']:
                        diff = Diff(app, last_evolution_sig, app_sig)
                        mutations = diff.evolution()
                    else:
                        mutations = get_mutations(app, last_evolution.version, 
                                                  last_evolution_sig, app_sig)
                    
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
                        except Exception, ex:
                            transaction.rollback()
                            print self.style.ERROR('Error during evolution of %s: %s' % (app_name, str(ex)))
                            sys.exit(1)
                        # Now update the evolution table
                        if options['hint']:
                            version = None
                        else:
                            version = last_evolution.version + 1
                        new_evolution = Evolution(app_name=app_name,
                                                  version=version,
                                                  signature=signature)
                        new_evolution.save()

                    else:
                        if options['compile']:
                            print ';; Compiled evolution SQL for %s' % app_name 
                            for s in sql:
                                print s                            
                        elif options['hint']:
                            print '--- Evolution hint for %s -------------------' % app_name
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
        if options['execute']:
            if verbosity > 0:
                print 'Evolution successful.'
        elif not options['compile'] and not options['hint']:
            if verbosity > 0:
                print "Trial evolution successful. Run './manage.py evolve --execute' to apply evolution."

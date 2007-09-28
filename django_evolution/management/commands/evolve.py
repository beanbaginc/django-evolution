from optparse import make_option
import sys
try:
    import cPickle as pickle
except ImportError:
    import pickle as pickle
    
from django.core.management.base import BaseCommand, CommandError
from django.db.models import get_apps, get_models, signals

from django_evolution.models import Evolution
from django_evolution.management.signature import create_app_dict
from django_evolution.management.sql import get_sql

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--verbosity', action='store', dest='verbosity', default='1',
            type='choice', choices=['0', '1', '2'],
            help='Verbosity level; 0=minimal output, 1=normal output, 2=all output'),
        make_option('--hint', action='store_false', dest='hint', default=False,
            help='Generate a sample '),
        make_option('-c','--compile', action='store_false', dest='compile', default=False,
            help='Compile a Django evolution script into SQL'),
        make_option('-s','--simulate', action='store_false', dest='compile', default=False,
            help='Perform a dry-run evolution to check that the migrations that are defined are complete'),
    )
    help = 'Evolve the models in a Django project.'
    args = ''

    requires_model_validation = False

    def handle(self, *args, **options):

        for app in get_apps():
            app_name = '.'.join(app.__name__.split('.')[:-1])
            app_dict = create_app_dict(app)
            signature = pickle.dumps(app_dict)

            evolutions = Evolution.objects.filter(app_name=app_name)
            if len(evolutions) > 0:
                last_evolution = evolutions[0]
                if last_evolution.signature != signature:
                    # Migration Required. Evolve the model.
                    print 'Migration Required - %s' % app_name
                    last_evolution_dict = pickle.loads(str(last_evolution.signature))
                    class_name = app_name + '.evolutions.evolution'
                    evolution_module = __import__(app_name + '.evolutions',{},{},[''])
                    sql = get_sql(evolution_module, 
                                  last_evolution.version, 
                                  len(evolution_module.SEQUENCE), 
                                  last_evolution_dict, 
                                  app_dict)
                    for s in sql:
                        print s
                    execute_sql(sql)
                    print 'Evolution Successful'
                else:
                    print 'Evolution not required for app %s' % app_name
            else:
                print "Can't evolve yet. Need to set a baseline syncdb."
                sys.exit(1)
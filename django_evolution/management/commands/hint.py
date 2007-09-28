from django.core.management.base import BaseCommand, CommandError
from django_evolution.management import hint

from optparse import make_option
import sys

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--verbosity', action='store', dest='verbosity', default='1',
            type='choice', choices=['0', '1', '2'],
            help='Verbosity level; 0=minimal output, 1=normal output, 2=all output'),
        make_option('--noinput', action='store_false', dest='interactive', default=True,
            help='Tells Django to NOT prompt the user for input of any kind.'),
    )
    help = 'Creates SQL hints to evolve the database to the specified version.'
    args = '[appname]'

    requires_model_validation = False

    def handle(self, appname=None, migration_name=None, *args, **options):
        from django.conf import settings
        from django.db.models import get_app, get_apps

        verbosity = int(options.get('verbosity', 1))
        if not appname or not migration_name:
            raise CommandError("An application name and a migration name is required.")
            
        hint(appname,migration_name)
    
        
        # interactive = options.get('interactive', True)
    
        # test_path = settings.TEST_RUNNER.split('.')
        # # Allow for Python 2.5 relative paths
        # if len(test_path) > 1:
        #     test_module_name = '.'.join(test_path[:-1])
        # else:
        #     test_module_name = '.'
        # test_module = __import__(test_module_name, {}, {}, test_path[-1])
        # test_runner = getattr(test_module, test_path[-1])
        # 
        # failures = test_runner(test_labels, verbosity=verbosity, interactive=interactive)
        # if failures:
        #     sys.exit(failures)

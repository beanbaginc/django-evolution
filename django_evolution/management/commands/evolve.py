from __future__ import print_function, unicode_literals

import logging
import os

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import CommandError
from django.db import connections, transaction
from django.db.utils import DEFAULT_DB_ALIAS

from django_evolution.compat.apps import get_apps, get_app
from django_evolution.compat.commands import BaseCommand
from django_evolution.compat.py23 import pickle_dumps, pickle_loads
from django_evolution.db.state import DatabaseState
from django_evolution.diff import Diff
from django_evolution.errors import EvolutionException
from django_evolution.evolve import get_unapplied_evolutions, get_mutations
from django_evolution.models import Version, Evolution
from django_evolution.mutations import AddField, DeleteApplication
from django_evolution.mutators import AppMutator
from django_evolution.signature import ProjectSignature
from django_evolution.utils import (execute_sql, get_app_label,
                                    get_evolutions_path, write_sql)


class Command(BaseCommand):
    help = 'Evolve the models in a Django project.'
    args = '<appname appname ...>'

    requires_model_validation = False

    def add_arguments(self, parser):
        """Add arguments to the command.

        Args:
            parser (object):
                The argument parser to add to.
        """
        parser.add_argument(
            '--noinput',
            action='store_false',
            dest='interactive',
            default=True,
            help='Tells Django to NOT prompt the user for input of any kind.')
        parser.add_argument(
            '--hint',
            action='store_true',
            dest='hint',
            default=False,
            help='Generate an evolution script that would update the app.')
        parser.add_argument(
            '--purge',
            action='store_true',
            dest='purge',
            default=False,
            help='Generate evolutions to delete stale applications.')
        parser.add_argument(
            '--sql',
            action='store_true',
            dest='compile_sql',
            default=False,
            help='Compile a Django evolution script into SQL.')
        parser.add_argument(
            '-w',
            '--write',
            metavar='EVOLUTION_NAME',
            action='store',
            dest='write_evolution_name',
            default=None,
            help='Write the generated evolutions to files with the given '
                 'evolution name in each affected app\'s "evolutions" paths.')
        parser.add_argument(
            '-x',
            '--execute',
            action='store_true',
            dest='execute',
            default=False,
            help='Apply the evolution to the database.')
        parser.add_argument(
            '--database',
            action='store',
            dest='database',
            help='Nominates a database to synchronize.')

    def handle(self, *app_labels, **options):
        try:
            self.evolve(*app_labels, **options)
        except CommandError:
            raise
        except Exception as e:
            logging.error('Unexpected error: %s' % e, exc_info=1)
            raise

    def evolve(self, *app_labels, **options):
        if not getattr(settings, 'DJANGO_EVOLUTION_ENABLED', True):
            raise CommandError(
                'Django Evolution is disabled for this project. Evolutions '
                'cannot be manually run.')

        self.hint = options['hint']
        self.write_evolution_name = options.get('write_evolution_name')
        self.verbosity = int(options['verbosity'])
        self.interactive = options['interactive']
        self.execute = options['execute']
        self.compile_sql = options['compile_sql']
        self.purge = options['purge']
        self.database = options['database']

        if not self.database:
            self.database = DEFAULT_DB_ALIAS

        if self.write_evolution_name and not self.hint:
            raise CommandError('--write cannot be used without --hint.')

        self.using_args = {
            'using': self.database
        }

        # Use the list of all apps, unless app labels are specified.
        if app_labels:
            if self.execute:
                raise CommandError('Cannot specify an application name when '
                                   'executing evolutions.')
            try:
                app_list = [get_app(app_label) for app_label in app_labels]
            except (ImproperlyConfigured, ImportError) as e:
                raise CommandError("%s. Are you sure your INSTALLED_APPS "
                                   "setting is correct?" % e)
        else:
            app_list = get_apps()

        # Iterate over all applications running the mutations
        self.evolution_required = False
        self.simulated = True
        self.new_evolutions = []
        self.written_hint_files = []

        self.database_state = DatabaseState(self.database)
        self.current_proj_sig = \
            ProjectSignature.from_database(self.database).serialize()
        self.current_signature = pickle_dumps(self.current_proj_sig)

        sql = []

        try:
            latest_version = \
                Version.objects.current_version(using=self.database)

            self.old_proj_sig = pickle_loads(latest_version.signature)
            self.diff = Diff(self.old_proj_sig, self.current_proj_sig)
        except Evolution.DoesNotExist:
            raise CommandError("Can't evolve yet. Need to set an "
                               "evolution baseline.")

        try:
            for app in app_list:
                app_sql = self.evolve_app(app)

                if app_sql:
                    sql.append((get_app_label(app), app_sql))

            # Process the purged applications if requested to do so.
            if self.purge:
                purge_sql = self.purge_apps()

                if purge_sql:
                    sql.append((None, purge_sql))
        except EvolutionException as e:
            raise CommandError(str(e))

        self.check_simulation()

        if self.evolution_required:
            self.perform_evolution(sql)
        elif self.verbosity > 0:
            self.stdout.write('No evolution required.\n')

    def evolve_app(self, app):
        app_label = get_app_label(app)
        sql = []

        if self.hint:
            evolutions = []
            hinted_evolution = self.diff.evolution()
            temp_mutations = hinted_evolution.get(app_label, [])
        else:
            evolutions = get_unapplied_evolutions(app, self.database)
            temp_mutations = get_mutations(app, evolutions, self.database)

        mutations = [
            mutation for mutation in temp_mutations
            if mutation.is_mutable(app_label, self.old_proj_sig,
                                   self.database_state, self.database)
        ]

        if mutations:
            app_sql = ['', '-- Evolve application %s' % app_label]
            self.evolution_required = True

            app_mutator = AppMutator(app_label, self.old_proj_sig,
                                     self.database_state, self.database)
            app_mutator.run_mutations(mutations)
            app_mutator_sql = app_mutator.to_sql()

            if self.compile_sql or self.execute:
                app_sql.extend(app_mutator_sql)

            if not app_mutator.can_simulate:
                self.simulated = False

            self.new_evolutions.extend(
                Evolution(app_label=app_label, label=label)
                for label in evolutions)

            if not self.execute:
                if self.compile_sql:
                    write_sql(app_sql, self.database)
                else:
                    hinted_evolution = (
                        '%s\n'
                        % self.generate_hint(app, app_label, mutations)
                    )

                    if self.hint and self.write_evolution_name:
                        evolutions_filename = \
                            os.path.join(get_evolutions_path(app),
                                         self.write_evolution_name + '.py')
                        assert evolutions_filename

                        self.written_hint_files.append((evolutions_filename,
                                                        hinted_evolution))
                    else:
                        self.stdout.write(hinted_evolution)

            sql.extend(app_sql)
        else:
            if self.verbosity > 1:
                self.stdout.write('Application %s is up to date\n' % app_label)

        return sql

    def purge_apps(self):
        sql = []

        if self.diff.deleted:
            self.evolution_required = True
            delete_app = DeleteApplication()
            purge_sql = []

            for app_label in self.diff.deleted:
                if delete_app.is_mutable(app_label, self.old_proj_sig,
                                         self.database_state,
                                         self.database):
                    app_mutator = AppMutator(app_label, self.old_proj_sig,
                                             self.database_state,
                                             self.database)
                    app_mutator.run_mutation(delete_app)
                    app_mutator_sql = app_mutator.to_sql()

                    if self.compile_sql or self.execute:
                        purge_sql.append('-- Purge application %s'
                                         % app_label)
                        purge_sql.extend(app_mutator_sql)

            if not self.execute:
                if self.compile_sql:
                    write_sql(purge_sql, self.database)
                else:
                    self.stdout.write(
                        'The following application(s) can be purged:\n')

                    for app_label in self.diff.deleted:
                        self.stdout.write('    %s\n' % app_label)

                    self.stdout.write('\n')

            sql.extend(purge_sql)
        else:
            if self.verbosity > 1:
                self.stdout.write('No applications need to be purged.\n')

        return sql

    def check_simulation(self):
        if self.simulated:
            diff = Diff(self.old_proj_sig, self.current_proj_sig)

            if not diff.is_empty(not self.purge):
                if self.hint:
                    self.stdout.write(self.style.ERROR(
                        'Your models contain changes that Django Evolution '
                        'cannot resolve automatically.\n'))
                    self.stdout.write(
                        'This is probably due to a currently unimplemented '
                        'mutation type.\n')
                    self.stdout.write(
                        'You will need to manually construct a mutation '
                        'to resolve the remaining changes.\n')
                else:
                    self.stdout.write(self.style.ERROR(
                        'The stored evolutions do not completely resolve '
                        'all model changes.\n'))
                    self.stdout.write(
                        'Run `./manage.py evolve --hint` to see a '
                        'suggestion for the changes required.\n')

                self.stdout.write(
                    '\n'
                    'The following are the changes that could not be '
                    'resolved:\n'
                    '%s\n'
                    % diff)

                raise CommandError('Your models contain changes that Django '
                                   'Evolution cannot resolve automatically.')
        else:
            self.stdout.write(self.style.NOTICE(
                'Evolution could not be simulated, possibly due to raw '
                'SQL mutations\n'))

    def perform_evolution(self, sql):
        if self.execute:
            # Now that we've worked out the mutations required,
            # and we know they simulate OK, run the evolutions
            if self.interactive:
                confirm = raw_input("""
You have requested a database evolution. This will alter tables
and data currently in the %r database, and may result in
IRREVERSABLE DATA LOSS. Evolutions should be *thoroughly* reviewed
prior to execution.

MAKE A BACKUP OF YOUR DATABASE BEFORE YOU CONTINUE!

Are you sure you want to execute the evolutions?

Type 'yes' to continue, or 'no' to cancel: """ % self.database)
            else:
                confirm = 'yes'

            if confirm.lower() == 'yes':
                connection = connections[self.database]
                connection.disable_constraint_checking()

                # Begin Transaction
                with connection.constraint_checks_disabled(), \
                     transaction.atomic(**self.using_args):
                    # TODO: Close the cursor when this succeeds/fails.
                    cursor = connection.cursor()
                    app_label = None

                    self.stdout.write(
                        '\n'
                        'This may take a while. Please be patient, and do not '
                        'cancel the upgrade!\n'
                        '\n')

                    try:
                        # Perform the SQL
                        for app_label, app_sql in sql:
                            if app_label and self.verbosity > 0:
                                self.stdout.write(
                                    'Applying database evolutions for %s...\n'
                                    % app_label)

                            execute_sql(cursor, app_sql, self.database)

                        # Now update the evolution table
                        version = Version(signature=self.current_signature)
                        version.save(**self.using_args)

                        for evolution in self.new_evolutions:
                            evolution.version = version
                            evolution.save(**self.using_args)
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                'Database evolutions for %s failed!'
                                % app_label))

                        if hasattr(e, 'last_sql_statement'):
                            self.stdout.write(
                                self.style.ERROR('The SQL statement was: %s'
                                                 % e.last_sql_statement))

                        self.stdout.write(
                            self.style.ERROR('The database error was: %s\n'
                                             % e))

                        raise CommandError(
                            'Error applying evolution for %s: %s'
                            % (app_label, e))

                if self.verbosity > 0:
                    self.stdout.write('Evolution successful.\n')
            else:
                self.stdout.write(self.style.ERROR('Evolution cancelled.\n'))
        elif not self.compile_sql and self.verbosity > 0 and self.simulated:
            self.stdout.write('Trial evolution successful.\n')

            if self.hint:
                if self.write_evolution_name:
                    self.stdout.write(
                        '\n'
                        'The following evolution files were written. '
                        'Verify the contents and add them\n'
                        'to the SEQUENCE lists in each __init__.py.\n\n')

                    for filename, hinted_evolution in self.written_hint_files:
                        evolutions_dir = os.path.dirname(filename)

                        if not os.path.exists(evolutions_dir):
                            os.mkdir(evolutions_dir, 0o755)

                        with open(filename, 'w') as fp:
                            fp.write(hinted_evolution)

                        self.stdout.write('  * %s\n'
                                          % os.path.relpath(filename))
            else:
                self.stdout.write("Run './manage.py evolve --execute' to "
                                  "apply evolution.\n")

    def generate_hint(self, app, app_label, mutations):
        imports = set()
        project_imports = set()
        mutation_types = set()

        app_prefix = app.__name__.split('.')[0]

        for m in mutations:
            mutation_types.add(m.__class__.__name__)

            if isinstance(m, AddField):
                field_module = m.field_type.__module__

                if field_module.startswith('django.db.models'):
                    imports.add('from django.db import models')
                else:
                    import_str = 'from %s import %s' % \
                                 (field_module, m.field_type.__name__)

                    if field_module.startswith(app_prefix):
                        project_imports.add(import_str)
                    else:
                        imports.add(import_str)

        lines = []

        if not self.write_evolution_name:
            lines.append('#----- Evolution for %s' % app_label)

        lines += [
            'from __future__ import unicode_literals',
            '',
        ]

        lines.append('from django_evolution.mutations import %s'
                     % ', '.join(sorted(mutation_types)))
        lines += sorted(imports)

        if project_imports:
            lines += [''] + sorted(project_imports)

        lines += [
            '',
            '',
            'MUTATIONS = [',
        ] + ['    %s,' % mutation for mutation in mutations] + [
            ']',
        ]

        if not self.write_evolution_name:
            lines.append('#----------------------')

        return '\n'.join(lines)

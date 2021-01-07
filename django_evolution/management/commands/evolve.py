"""Management command for applying, inspecting, and hinting evolutions."""

from __future__ import print_function, unicode_literals

import textwrap
import os

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import CommandError
from django.db.utils import DEFAULT_DB_ALIAS
from django.dispatch import receiver
from django.utils.translation import ngettext, ugettext as _

from django_evolution.compat import six
from django_evolution.compat.apps import get_app
from django_evolution.compat.commands import BaseCommand
from django_evolution.compat.six.moves import input
from django_evolution.errors import EvolutionException
from django_evolution.evolve import EvolveAppTask, Evolver, PurgeAppTask
from django_evolution.signals import (applied_evolution,
                                      applied_migration,
                                      applying_evolution,
                                      applying_migration,
                                      created_models,
                                      creating_models)
from django_evolution.utils.apps import import_management_modules
from django_evolution.utils.evolutions import get_evolutions_path
from django_evolution.utils.sql import SQLExecutor


class Command(BaseCommand):
    """Manages and applies evolutions to the database."""

    help = 'Manage evolutions to the database schema based on model changes.'
    args = '<appname appname ...>'

    requires_model_validation = False

    def add_arguments(self, parser):
        """Add arguments to the command.

        Args:
            parser (object):
                The argument parser to add to.
        """
        parser.add_argument(
            'args',
            metavar='APP_LABEL',
            nargs='*',
            help=_('One or more app labels to evolve.'))
        parser.add_argument(
            '--noinput',
            action='store_false',
            dest='interactive',
            default=True,
            help=_('Automatically says yes to any prompts. When used with '
                   '--execute, this will apply evolutions without first '
                   'asking for confirmation.'))
        parser.add_argument(
            '--hint',
            action='store_true',
            dest='hint',
            default=False,
            help=_('Display sample evolutions covering any new changes made '
                   'to models since the last evolution.'))
        parser.add_argument(
            '--purge',
            action='store_true',
            dest='purge',
            default=False,
            help=_('Purge deleted applications from the evolution history.'))
        parser.add_argument(
            '--sql',
            action='store_true',
            dest='compile_sql',
            default=False,
            help=_('Display the evolutions as SQL.'))
        parser.add_argument(
            '-w',
            '--write',
            metavar='EVOLUTION_NAME',
            action='store',
            dest='write_evolution_name',
            default=None,
            help=_('Write the generated evolutions to files with the given '
                   'evolution name in each affected app\'s "evolutions" '
                   'paths.'))
        parser.add_argument(
            '-x',
            '--execute',
            action='store_true',
            dest='execute',
            default=False,
            help=_('Apply evolutions to the database.'))
        parser.add_argument(
            '--database',
            action='store',
            dest='database',
            help=_('Specify the database containing models to synchronize.'))

    def handle(self, *app_labels, **options):
        """Handle the command.

        This will validate the arguments and run through the evolution
        process.

        Args:
            app_labels (list of unicode):
                The app labels to evolve.

            options (dict):
                Options parsed by the argument parser.

        Raises:
            django.core.management.base.CommandError:
                Arguments were invalid or something went wrong. Details are
                in the message.
        """
        if not getattr(settings, 'DJANGO_EVOLUTION_ENABLED', True):
            raise CommandError(
                _('Django Evolution is disabled for this project. '
                  'Evolutions cannot be manually run.'))

        self.purge = options['purge']
        self.verbosity = int(options['verbosity'])

        hint = options['hint']
        compile_sql = options['compile_sql']
        database_name = options['database'] or DEFAULT_DB_ALIAS
        execute = options['execute']
        interactive = options['interactive']
        write_evolution_name = options['write_evolution_name']

        if app_labels and self.execute:
            raise CommandError(
                _('Cannot specify an application name when executing '
                  'evolutions.'))

        if write_evolution_name and not hint:
            raise CommandError(_('--write cannot be used without --hint.'))

        import_management_modules()

        try:
            self.evolver = Evolver(database_name=database_name,
                                   hinted=hint,
                                   verbosity=self.verbosity,
                                   interactive=interactive)

            # Figure out what tasks we need to add to the evolver. This
            # must be done before we check any state (as that will finalize
            # the task list).
            self._add_tasks(app_labels)

            # Calculate some information we may need later.
            self.active_purge_tasks = [
                task
                for task in self.evolver.tasks
                if isinstance(task, PurgeAppTask) and len(task.sql) > 0
            ]

            # Display any additional information on the evolution process
            # the caller may be interested in.
            if self.verbosity > 1:
                self._display_extra_task_details()

            # Simulate the evolutions to make sure that they'll get us to the
            # target database state. This will raise a CommandError with
            # helpful information if the evolutions don't get us there, or
            # if one or more evolutions couldn't be simulated.
            simulated = self._check_simulation()

            if not self.evolver.get_evolution_required():
                if self.verbosity > 0:
                    self.stdout.write(_('No database upgrade required.\n'))
            elif execute:
                if not interactive or self._confirm_execute():
                    self._perform_evolution()
                else:
                    self.stderr.write(_('Database upgrade cancelled.\n'))
            elif compile_sql:
                self._display_compiled_sql()
            else:
                # Be helpful and list any applications that can be purged,
                # and then show any evolution content that may be useful to
                # the user.
                self._display_available_purges()
                self._generate_evolution_contents(write_evolution_name)

                if simulated:
                    if self.verbosity > 0:
                        self.stdout.write(_('Trial upgrade successful!\n'))

                    if not self.evolver.hinted and self.verbosity > 0:
                        self.stdout.write(_(
                            'Run `./manage.py evolve --execute` to apply '
                            'the evolution.\n'))
        except EvolutionException as e:
            raise CommandError(six.text_type(e))

    def _add_tasks(self, app_labels):
        """Add tasks to the evolver, based on the command options.

        This will queue up the applications that need to be evolved, and
        queue up the purging of stale applications if requested.

        Args:
            app_labels (list of unicode):
                The list of app labels to evolve. If this is empty, all
                registered apps will be evolved.
        """
        evolver = self.evolver

        if app_labels:
            # The caller wants to evolve specific apps. Queue each one,
            # handling any invalid app labels in the process.
            try:
                for app_label in app_labels:
                    evolver.queue_evolve_app(get_app(app_label))
            except (ImportError, ImproperlyConfigured) as e:
                raise CommandError(
                    _('%s. Are you sure your INSTALLED_APPS setting is '
                      'correct?')
                    % e)
        else:
            # The caller wants the default behavior of evolving all apps
            # with pending evolutions.
            evolver.queue_evolve_all_apps()

        if self.purge:
            # The caller wants to purge all old stale applications that
            # no longer exist.
            #
            # Note that we don't do this by default, since those apps
            # might not be permanently added to the list of installed apps.
            evolver.queue_purge_old_apps()

    def _display_extra_task_details(self):
        """Display some informative state about queued tasks.

        This will list any applications that are already up-tp-date, and
        list whether or not any applications need to be purged.
        """
        # List all applications that appear up-to-date.
        for task in self.evolver.tasks:
            if (isinstance(task, EvolveAppTask) and
                not task.evolution_required):
                self.stdout.write(_('Application "%s" is up-to-date\n')
                                  % task.app_label)

        if self.purge and not self.active_purge_tasks:
            # List whether there are any applications that need to be
            # purged.
            self.stdout.write(_('No applications need to be purged.\n'))

    def _check_simulation(self):
        """Check the results of a simulation.

        This will check first if a simulation could even occur (based on
        whether there are raw SQL mutations that are going to be applied). If a
        simulation did occur, information on the simulation results and
        the resulting signature diff will be displayed.

        If a simulation either could not be performed, or was performed and
        succeeded, a result will be returned so that the caller can perform
        additional operations based on that state.

        If a simulation could be performed but failed, this will immediately
        terminate the command with an error message.

        Returns:
            bool:
            ```True`` if the simulation was successful and all changes were
            resolved. ``False`` if a simulation could not be performed due to
            raw SQL mutations.

        Raises:
            django.core.management.base.CommandError:
                A simulation was performed, but changes could not be resolved.
        """
        if not self.evolver.can_simulate():
            self.stdout.write(self.style.NOTICE(
                _('Evolution could not be simulated, possibly due '
                  'to raw SQL mutations\n')))

            return False

        diff = self.evolver.diff_evolutions()

        if diff.is_empty(ignore_apps=not self.purge):
            return True

        if self.evolver.hinted:
            self.stderr.write(self._wrap_paragraphs(_(
                'Your models contain changes that Django Evolution '
                'cannot resolve automatically.\n'
                '\n'
                'This is probably due to a currently unimplemented '
                'mutation type. You will need to manually construct a '
                'mutation to resolve the remaining changes.')))
        else:
            self.stderr.write(self._wrap_paragraphs(_(
                'The stored evolutions do not completely resolve '
                'all model changes.\n'
                '\n'
                'Run `./manage.py evolve --hint` to see a '
                'suggestion for the changes required.')))

        self.stdout.write('\n\n')
        self.stdout.write(self._wrap_paragraphs(_(
            'The following are the changes that could not be resolved:')))
        self.stdout.write('\n%s\n' % diff)

        raise CommandError(_(
            'Your models contain changes that Django Evolution cannot '
            'resolve automatically.'))

    def _confirm_execute(self):
        """Prompt the user to confirm execution of an evolution.

        This will warn the user of the risks of evolving the database and
        to recommend a backup. It will then prompt for confirmation, returning
        the result.

        Returns:
            bool:
            ``True`` if the user confirmed the execution. ``False`` if the
            execution should be cancelled.
        """
        prompt = self._wrap_paragraphs(
            _('You have requested a database upgrade. This will alter '
              'tables and data currently in the "%s" database, and may '
              'result in IRREVERSABLE DATA LOSS. Upgrades should be '
              '*thoroughly* reviewed and tested prior to execution.\n'
              '\n'
              'MAKE A BACKUP OF YOUR DATABASE BEFORE YOU CONTINUE!\n'
              '\n'
              'Are you sure you want to execute the database upgrade?\n'
              '\n'
              'Type "yes" to continue, or "no" to cancel:')
            % self.evolver.database_name)

        # Note that we must append a space here, rather than above, since the
        # paragraph wrapping logic will strip trailing whitespace.
        return input('%s ' % prompt).lower() == 'yes'

    def _perform_evolution(self):
        """Perform the evolution.

        This will perform the evolution, based on the options passed to this
        command. Progress on the evolution will be printed to the console.

        Raises:
            django.core.management.base.CommandError:
                The evolution failed.
        """
        evolver = self.evolver
        verbosity = self.verbosity

        if verbosity > 0:
            @receiver(applying_evolution, sender=evolver)
            def _on_applying_evolution(task, evolutions, **kwargs):
                if verbosity > 2:
                    message = (
                        _('Applying database evolutions for %(app_label)s '
                          '(%(evolution_labels)s)...\n')
                        % {
                            'app_label': task.app_label,
                            'evolution_labels': ', '.join(
                                evolution.label
                                for evolution in evolutions
                            ),
                        }
                    )
                else:
                    message = (
                        _('Applying database evolutions for '
                          '%(app_label)s...\n')
                        % {
                            'app_label': task.app_label,
                        }
                    )

                self.stdout.write(message)

            @receiver(applying_migration, sender=evolver)
            def _on_applying_migration(migration, **kwargs):
                self.stdout.write(
                    _('Applying database migration %(migration_name)s for '
                      '%(app_label)s...\n')
                    % {
                        'app_label': migration.app_label,
                        'migration_name': migration.name,
                    })

            @receiver(creating_models, sender=evolver)
            def _on_creating_models(app_label, model_names, **kwargs):
                if verbosity > 2:
                    message = (
                        _('Creating new database models for %(app_label)s '
                          '(%(model_names)s)...\n')
                        % {
                            'app_label': app_label,
                            'model_names': ', '.join(model_names),
                        }
                    )
                else:
                    message = (
                        _('Creating new database models for '
                          '%(app_label)s...\n')
                        % {
                            'app_label': app_label,
                        }
                    )

                self.stdout.write(message)

        if verbosity > 1:
            @receiver(applied_evolution, sender=evolver)
            def _on_applied_evolution(task, evolutions, **kwargs):
                if verbosity > 2:
                    message = (
                        _('Successfully applied database evolutions for '
                          '%(app_label)s (%(evolution_labels)s).\n')
                        % {
                            'app_label': task.app_label,
                            'evolution_labels': ', '.join(
                                evolution.label
                                for evolution in evolutions
                            ),
                        }
                    )
                else:
                    message = (
                        _('Successfully applied database evolutions for '
                          '%(app_label)s.\n')
                        % {
                            'app_label': task.app_label,
                        }
                    )

                self.stdout.write(message)

            @receiver(applied_migration, sender=evolver)
            def _on_applied_migration(migration, **kwargs):
                self.stdout.write(
                    _('Successfully applied database migration '
                      '%(migration_name)s for %(app_label)s.\n')
                    % {
                        'app_label': migration.app_label,
                        'migration_name': migration.name,
                    })

            @receiver(created_models, sender=evolver)
            def _on_created_models(app_label, model_names, **kwargs):
                if verbosity > 2:
                    message = (
                        _('Successfully created new database models for '
                          '%(app_label)s (%(model_names)s).\n')
                        % {
                            'app_label': app_label,
                            'model_names': ', '.join(model_names),
                        }
                    )
                else:
                    message = (
                        _('Successfully created new database models for '
                          '%(app_label)s.\n')
                        % {
                            'app_label': app_label,
                        }
                    )

                self.stdout.write(message)

        self.stdout.write(
            '\n%s\n\n'
            % self._wrap_paragraphs(_(
                'This may take a while. Please be patient, and DO NOT '
                'cancel the upgrade!')))

        try:
            evolver.evolve()
        except EvolutionException as e:
            self.stderr.write('%s\n' % e)

            if getattr(e, 'last_sql_statement', None):
                self.stderr.write(
                    _('The SQL statement that failed was: %s\n')
                    % (e.last_sql_statement,))

            raise CommandError(six.text_type(e))

        if verbosity > 0:
            self.stdout.write(_('The database upgrade was successful!\n'))

    def _display_compiled_sql(self):
        """Display the compiled SQL for the evolution run.

        This will output the SQL that would be executed based on the options
        passed to the command.
        """
        database_name = self.evolver.database_name

        with SQLExecutor(database=database_name) as executor:
            for i, task in enumerate(self.evolver.tasks):
                if task.sql:
                    if i > 0:
                        self.stdout.write('\n')

                    self.stdout.write('-- %s\n' % task)

                    for statement in executor.run_sql(task.sql, capture=True):
                        self.stdout.write('%s\n' % statement)

    def _display_available_purges(self):
        """Display the apps that can be purged."""
        purge_tasks = self.active_purge_tasks

        if purge_tasks:
            self.stdout.write(
                ngettext('The following application can be purged:',
                         'The following applications can be purged:',
                         len(purge_tasks)))
            self.stdout.write('\n')

            for purge_task in purge_tasks:
                self.stdout.write('    * %s\n' % purge_task.app_label)

            self.stdout.write('\n')
        elif self.verbosity > 1:
            self.stdout.write(_('No applications need to be purged.\n'))

    def _generate_evolution_contents(self, evolution_label=None):
        """Generate the contents of evolution files or hinted evolutions.

        This will grab the contents of either the stored evolution files
        or hinted evolutions (if using ``--hint``) and write them to the
        console or to generated evolution files (if using ``--write``).

        Args:
            evolution_label (unicode, optional):
                The label used as a base for any generated filenames.
                If provided, the filenames will be written to the appropriate
                evolution directories, with a ``.py`` appended.

        Raises:
            django.core.management.base.CommandError:
                An evolution file couldn't be written. Details are in the
                error message.
        """
        evolution_contents = self.evolver.iter_evolution_content()

        if evolution_label:
            # We're writing the hinted evolution files to disk. Notify the user
            # and begin writing.
            verbosity = self.verbosity

            if verbosity > 0:
                self.stdout.write('\n%s\n\n' % self._wrap_paragraphs(_(
                    'The following evolution files were written. Verify the '
                    'contents and add them to the SEQUENCE lists in each '
                    '__init__.py.')))

            for task, content in evolution_contents:
                assert hasattr(task, 'app')

                dirname = get_evolutions_path(task.app)
                filename = os.path.join(dirname, '%s.py' % evolution_label)

                if not os.path.exists(dirname):
                    try:
                        os.mkdir(dirname, 0o755)
                    except IOError as e:
                        raise CommandError(
                            _('Unable to create evolutions directory "%s": %s')
                            % (dirname, e))

                try:
                    with open(filename, 'w') as fp:
                        fp.write(content.strip())
                        fp.write('\n')
                except Exception as e:
                    raise CommandError(
                        _('Unable to write evolution file "%s": %s')
                        % (filename, e))

                if verbosity > 0:
                    self.stdout.write('  * %s\n' % os.path.relpath(filename))
        else:
            # We're just going to output the hint content.
            for i, (task, content) in enumerate(evolution_contents):
                assert hasattr(task, 'app_label')

                self.stdout.write('#----- Evolution for %s\n' % task.app_label)
                self.stdout.write(content.strip())
                self.stdout.write('#----------------------\n')

            self.stdout.write('\n')

    def _wrap_paragraphs(self, text):
        """Wrap a block of text into paragraphs.

        This will take paragraphs worth of text and wrap them to fit in a
        standard terminal width, helping provide more readable output.

        Args:
            text (unicode):
                The text to wrap.

        Returns:
            unicode:
            The wrapped text.
        """
        return '\n'.join(
            textwrap.fill(paragraph)
            for paragraph in text.splitlines()
        )

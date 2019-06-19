"""Replacement for Django's migrate command."""

from __future__ import unicode_literals

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils.translation import ugettext as _

try:
    from django.core.management.commands.migrate import Command as BaseCommand
    has_migrate = True
except ImportError:
    from django_evolution.compat.commands import BaseCommand
    has_migrate = False


class Command(BaseCommand):
    """Command for working with Django migrations.

    This wraps the original ``migrate`` command. If Django Evolution is
    enabled, this will call ``evolve`` with the necessary parameters for the
    ``migrate`` call. If disabled, this will call Django's ``migrate``.

    There are some differences in our ``migrate``:

    * ``--fake`` is not supported, and will show an error if used.
    * ``--run-syncdb`` and ``--fake-initial`` are always implied, and cannot
      be turned off.
    * ``initial_data`` fixtures are not loaded (they were removed in
      Django 1.9 anyway).
    * ``--no-initial-data`` isn't directly handled, but since initial data
      isn't supported, that doesn't impact anything.
    """

    def handle(self, *args, **options):
        """Handle the command.

        This will validate the arguments and run through the evolution
        process.

        Args:
            *args (list of unicode):
                Positional arguments passed on the command line.

            **options (dict):
                Options parsed by the argument parser.

        Raises:
            django.core.management.base.CommandError:
                Arguments were invalid or something went wrong. Details are
                in the message.
        """
        if not has_migrate:
            raise CommandError(
                _('migrate is not available on this version of Django. '
                  'Use `syncdb` instead.'))

        if not getattr(settings, 'DJANGO_EVOLUTION_ENABLED', True):
            # Run the original migrate command.
            return super(Command, self).handle(*args, **options)

        if options.get('migration_name'):
            raise CommandError(
                _('The migrate command cannot apply a specific migration '
                  'name when Django Evolution is in use. Set '
                  '`DJANGO_EVOLUTION_ENABLED = False` in your settings.py '
                  'to use the original migrate command.'))

        if options.get('fake'):
            raise CommandError(
                _('The migrate command cannot use --fake when Django '
                  'Evolution is in use. Set '
                  '`DJANGO_EVOLUTION_ENABLED = False` in your settings.py '
                  'to use the original migrate command.'))

        app_labels = []

        if options.get('app_label'):
            app_labels.append(options.get('app_label'))

        call_command('evolve',
                     *app_labels,
                     verbosity=options.get('verbosity'),
                     interactive=options.get('interactive'),
                     database=options.get('database'),
                     execute=True)

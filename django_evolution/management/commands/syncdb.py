"""Replacement for Django's syncdb command."""

from __future__ import unicode_literals

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils.translation import ugettext as _

try:
    from django.core.management.commands.syncdb import Command as BaseCommand
    has_syncdb = True
except ImportError:
    from django_evolution.compat.commands import BaseCommand
    has_syncdb = False


class Command(BaseCommand):
    """Legacy command for synchronizing database models.

    This wraps the original ``syncdb`` command. If Django Evolution is enabled,
    this will call ``evolve`` with the necessary parameters for the ``syncdb``
    call. If disabled, this will call Django's ``syncdb``.

    There are some differences in our ``syncdb``:

    * ``initial_data`` fixtures are not loaded.
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
        if not has_syncdb:
            raise CommandError(
                _('syncdb is not available on this version of Django. '
                  'Use `migrate` instead.'))

        if not getattr(settings, 'DJANGO_EVOLUTION_ENABLED', True):
            # Run the original syncdb command.
            return super(Command, self).handle(*args, **options)

        call_command('evolve',
                     verbosity=options.get('verbosity'),
                     interactive=options.get('interactive'),
                     database=options.get('database'),
                     execute=True)

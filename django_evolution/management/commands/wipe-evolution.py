from __future__ import print_function, unicode_literals

from django.core.management.base import CommandError
from django.db.models import Q

from django_evolution.compat.commands import BaseCommand
from django_evolution.compat.six.moves import input
from django_evolution.compat.translation import gettext as _
from django_evolution.models import Evolution


class Command(BaseCommand):
    """Wipes an evolutions from the history.

    This is a very dangerous operation, and should only be done after a
    full database backup.
    """

    def add_arguments(self, parser):
        """Add arguments to the command.

        Args:
            parser (object):
                The argument parser to add to.
        """
        parser.add_argument(
            'args',
            metavar='EVOLUTION_LABEL',
            nargs='+',
            help=_('One or more evolution labels to wipe.'))
        parser.add_argument(
            '--noinput',
            action='store_false',
            dest='interactive',
            default=True,
            help='Tells Django to NOT prompt the user for input of any kind.')
        parser.add_argument(
            '--app-label',
            action='store',
            dest='app_label',
            help='The app label the evolution label applies to.')

    def handle(self, *evolution_labels, **options):
        if not evolution_labels:
            raise CommandError(
                'One or more evolution labels must be provided.')

        # Sanity-check each app to make sure it exists only once, and is
        # in the given app (if specified).
        to_wipe_ids = []
        app_label = options['app_label']

        for evolution_label in evolution_labels:
            q = Q(label=evolution_label)

            if app_label:
                q = q & Q(app_label=app_label)

            evolutions = list(Evolution.objects.filter(q).values('pk'))

            if len(evolutions) == 0:
                if app_label:
                    raise CommandError(
                        "Unable to find evolution '%s' for app label '%s'" %
                        (evolution_label, app_label))
                else:
                    raise CommandError(
                        "Unable to find evolution '%s'" % evolution_label)
            if len(evolutions) > 1:
                if app_label:
                    raise CommandError(
                        "Too many evolutions named '%s' for app label '%s'" %
                        (evolution_label, app_label))
                else:
                    raise CommandError(
                        "Too many evolutions named '%s'" % evolution_label)

            to_wipe_ids.append(evolutions[0]['pk'])

        if to_wipe_ids:
            if options['interactive']:
                confirm = input("""
You have requested to delete %s evolution(s). This may cause permanent
problems, and should only be done after a FULL BACKUP and under direct
guidance.

Are you sure you want to wipe these evolutions from the database?

Type 'yes' to continue, or 'no' to cancel: """ % len(to_wipe_ids))
            else:
                confirm = 'yes'

            if confirm == 'yes':
                Evolution.objects.filter(pk__in=to_wipe_ids).delete()

                print('%s evolution(s) have been deleted.' % len(to_wipe_ids))

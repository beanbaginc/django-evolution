"""Management command for marking evolutions as applied.

Version Added:
    2.3
"""

from __future__ import print_function, unicode_literals

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import CommandError

from django_evolution.compat.apps import get_app
from django_evolution.compat.commands import BaseCommand
from django_evolution.compat.six.moves import input
from django_evolution.compat.translation import gettext as _
from django_evolution.models import Evolution, Version
from django_evolution.utils.evolutions import get_evolution_sequence


class Command(BaseCommand):
    """Mark one or more evolutions as applied to a database.

    This is almost never a good idea to run, and should only be run if
    repairing a database schema.

    Version Added:
        2.3
    """

    help = _(
        "Marks one or more evolutions as applied in the database.\n"
        "\n"
        "This is an advanced command that should only be used if you know "
        "what you're doing, or are guided by support as part of a database "
        "repair."
    )

    def add_arguments(self, parser):
        """Add arguments to the command.

        Args:
            parser (object):
                The argument parser to add to.
        """
        parser.add_argument(
            'args',
            metavar='EVOLUTION_LABEL',
            nargs='*',
            help=_('One or more evolution labels to mark as applied. '
                   'This is required if --all isn\'t specified.'))
        parser.add_argument(
            '--noinput',
            action='store_false',
            dest='interactive',
            default=True,
            help=_('Tells Django to NOT prompt the user for input of any '
                   'kind.'))
        parser.add_argument(
            '--app-label',
            action='store',
            dest='app_label',
            help=_('The app label the evolution labels apply to.'))
        parser.add_argument(
            '--all',
            action='store_true',
            default=False,
            dest='apply_all',
            help=_('Marks all unapplied evolutions as applied. This should '
                   'only if you know what you are doing.'))

    def handle(self, *evolution_labels, **options):
        """Handle the command.

        This will validate the arguments and mark the evolutions as applied.

        Args:
            evolution_labels (list of unicode):
                The evolution labels to mark as applied.

            options (dict):
                Options parsed by the argument parser.

        Raises:
            django.core.management.base.CommandError:
                Arguments were invalid or something went wrong. Details are
                in the message.
        """
        apply_all = options['apply_all']

        if not evolution_labels and not apply_all:
            raise CommandError(
                _('One or more evolution labels must be provided.'))

        app_label = options['app_label']

        if not app_label:
            raise CommandError(_('--app-label must be specified.'))

        try:
            app = get_app(app_label)
        except ImproperlyConfigured:
            raise CommandError(_('"%s" is not a registered Django app.')
                               % app_label)

        sequence = set(get_evolution_sequence(app))

        # Check that each provided evolution label is known in the sequence.
        if apply_all:
            evolution_labels = sequence
        else:
            for evolution_label in evolution_labels:
                if evolution_label not in sequence:
                    raise CommandError(
                        _('"%(evolution_label)s" is not a known evolution in '
                          '"%(app_label)s".')
                        % {
                            'app_label': app_label,
                            'evolution_label': evolution_label,
                        })

        # Check whether any of these evolutions are already marked as applied.
        found_evolutions = (
            Evolution.objects
            .filter(app_label=app_label, label__in=evolution_labels)
            .values_list('label', flat=True)
        )

        if found_evolutions:
            raise CommandError(
                _('The following evolutions are already applied: %s')
                % ', '.join(sorted(found_evolutions))
            )

        if options['interactive']:
            confirm = input(_("""
You are marking %s evolution(s) as applied. This is usually a BAD IDEA,
as it may BREAK FUTURE UPGRADES. Only use this if you are repairing the
Django Evolution history under guidance from someone familiar with this
kind of repair.

Please BACK UP FIRST!

Are you sure you want to mark these evolutions as applied?

Type 'yes' to continue, or 'no' to cancel: """) % len(evolution_labels))
        else:
            confirm = 'yes'

        if confirm == 'yes':
            version = Version.objects.current_version()

            Evolution.objects.bulk_create(
                Evolution(version=version,
                          app_label=app_label,
                          label=evolution_label)
                for evolution_label in evolution_labels
            )

            self.stdout.write(self.style.SUCCESS(
                _('%s evolution(s) have been marked as applied.')
                % len(evolution_labels)))

"""Management command for working with project signatures.

Version Added:
    2.3
"""

from __future__ import print_function, unicode_literals

import json
import textwrap

from django.core.management.base import CommandError

from django_evolution.compat.commands import BaseCommand
from django_evolution.compat.six.moves import input
from django_evolution.compat.translation import gettext as _
from django_evolution.models import Evolution, Version


class Command(BaseCommand):
    """List, show, or remove project signatures from the history.

    Version Added:
        2.3
    """

    help = _(
        "List, show, or remove project signatures from the history.\n"
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
        # Ideally we'd use subcommands for the various actions, but we still
        # support versions of Django that use optparse, so we're a bit limited.
        parser.add_argument(
            '--show',
            action='store_true',
            dest='action_show',
            help=_('Show a project signature.'))
        parser.add_argument(
            '--delete',
            action='store_true',
            dest='action_delete',
            help=_('Delete a project signature. Requires --id.'))
        parser.add_argument(
            '--list',
            action='store_true',
            dest='action_list',
            help=_('List the registered project signatures.'))
        parser.add_argument(
            '--noinput',
            action='store_false',
            dest='interactive',
            default=True,
            help=_('Tells Django to NOT prompt the user for input of any '
                   'kind.'))

        parser.add_argument(
            '--id',
            type=int,
            default=None,
            help=_('The signature version ID to operate on.'))

    def handle(self, **options):
        """Run the management command.

        Args:
            options (dict):
                The parsed command line options.

        Raises:
            django.core.management.base.CommandError:
                Arguments were invalid or something went wrong. Details are
                in the message.
        """
        action_list = options['action_list']
        action_show = options['action_show']
        action_delete = options['action_delete']

        # Check if more than one action is specified.
        num_enabled_actions = sum(
            int(_action)
            for _action in (action_list, action_show, action_delete)
        )

        if num_enabled_actions > 1:
            raise CommandError('Only one action (--show, --delete, or --list) '
                               'can be specified.')

        if num_enabled_actions == 0:
            action_show = True

        interactive = options['interactive']

        if action_show:
            self._show_signature(version_id=options['id'])
        elif action_delete:
            self._delete_signature(version_id=options['id'],
                                   interactive=interactive)
        elif action_list:
            self._list_signatures()

    def _show_signature(self, version_id):
        """Output a project signature.

        Args:
            version_id (int):
                The ID of the signature version to show. If ``None``, the
                current version will be shown.

        Raises:
            django.core.management.base.CommandError:
                The project signature does not exist.
        """
        if version_id is None:
            version = Version.objects.current_version()
        else:
            try:
                version = Version.objects.get(pk=version_id)
            except Version.DoesNotExist:
                raise CommandError('Signature version ID "%s" does not exist.'
                                   % version_id)

        self.stdout.write(json.dumps(version.signature.serialize(),
                                     indent=2,
                                     sort_keys=True))

    def _delete_signature(self, version_id, interactive):
        """Delete a project signature from the database.

        This will prompt for confirmation before wiping.

        Args:
            version_id (int):
                The ID of the signature version to delete. If ``None``, the
                current version will be shown.

            interactive (bool):
                Whether this can prompt for confirmation before deleting.

        Raises:
            django.core.management.base.CommandError:
                The project signature does not exist.
        """
        if version_id is None:
            raise CommandError('--id must be specified.')

        try:
            version = Version.objects.get(pk=version_id)
        except Version.DoesNotExist:
            raise CommandError('Signature version ID "%s" does not exist.'
                               % version_id)

        if interactive:
            evolution_labels = [
                '%s.%s' % (_app_label, _label)
                for _app_label, _label in (
                    version.evolutions.values_list('app_label', 'label')
                )
            ]

            lines = [
                'WARNING: This will permanently delete the stored signature, '
                'which may break your database and prevent future upgrades. '
                'Unless you are developing with Django Evolution, or have '
                'been told to do this by the developer of the software you '
                'are trying to upgrade, DO NOT DO THIS!',
            ]

            if evolution_labels:
                lines += [
                    'This will also delete the following evolution records '
                    'from the database:',

                    '\n'.join(
                        '* %s' % _evolution_label
                        for _evolution_label in evolution_labels
                    ),
                ]

            lines += [
                'MAKE A BACKUP OF YOUR DATABASE BEFORE YOU CONTINUE!',

                'Are you sure you want to delete this signature?',

                'Type "yes" to continue, or "no" to cancel:',
            ]

            prompt = self._wrap_paragraphs('\n\n'.join(lines))

            confirmed = (input('%s ' % prompt).lower() == 'yes')
        else:
            confirmed = True

        if confirmed:
            version.delete()

            self.stdout.write(self.style.SUCCESS(
                _('Signature version ID %s deleted.')
                % version_id))

    def _list_signatures(self):
        """Display the list of all project signatures.

        This will show the project signature IDs, timestamps, and any
        evolutions that apply to the signature.
        """
        versions = (
            Version.objects
            .only('id', 'when')
            .values_list('id', 'when')
            .order_by('id')
        )

        versions_to_evolutions = {}
        evolutions_to_labels = {}

        for evolution in Evolution.objects.all():
            evolutions_to_labels[evolution.pk] = \
                '%s.%s' % (evolution.app_label, evolution.label)
            versions_to_evolutions.setdefault(evolution.version_id, []).append(
                evolution.pk)

        for pk, when in versions:
            evolution_ids = versions_to_evolutions.get(pk, [])

            if evolution_ids:
                evolution_labels = [
                    evolutions_to_labels[_evolution_id]
                    for _evolution_id in evolution_ids
                ]
            else:
                evolution_labels = ''

            leader = '% 4s - %s - ' % (pk,
                                       when.strftime('%Y-%m-%d %H:%M:%S.%f'))

            if evolution_labels:
                self.stdout.write('%s%s' % (leader, evolution_labels[0]))

                for evolution_label in evolution_labels[1:]:
                    self.stdout.write('%s%s' % (' ' * len(leader),
                                                evolution_label))
            else:
                self.stdout.write(leader)

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

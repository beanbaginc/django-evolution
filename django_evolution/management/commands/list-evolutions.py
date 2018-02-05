from __future__ import print_function, unicode_literals

from django_evolution.compat.apps import get_apps
from django_evolution.compat.commands import BaseCommand
from django_evolution.models import Evolution
from django_evolution.utils import get_app_label


class Command(BaseCommand):
    """Lists the applied evolutions for one or more apps."""

    def handle(self, *app_labels, **options):
        if not app_labels:
            app_labels = [get_app_label(app) for app in get_apps()]

        for app_label in app_labels:
            evolutions = list(Evolution.objects.filter(app_label=app_label))

            if evolutions:
                print("Applied evolutions for '%s':" % app_label)

                for evolution in evolutions:
                    print('    %s' % evolution.label)

                print()

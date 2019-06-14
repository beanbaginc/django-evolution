"""Constants used throughout Django Evolution."""

from __future__ import unicode_literals


class UpgradeMethod(object):
    """Upgrade methods available for an application."""

    #: The app is upgraded through Django Evolution.
    EVOLUTIONS = 'evolutions'

    #: The app is upgraded through Django Migrations.
    MIGRATIONS = 'migrations'

from __future__ import unicode_literals

from django.conf import settings


class EvolutionOperationsMulti(object):
    def __init__(self, db_name, database_state=None):
        """Initialize the instance.

        Args:
            db_name (unicode):
                The name of the database.

            database_state (django_evolution.db.state.DatabaseState):
                The database state to track information through.
        """
        if database_state is None:
            from django_evolution.db.state import DatabaseState
            database_state = DatabaseState(db_name, scan=False)

        try:
            from django.db import connections
            engine = settings.DATABASES[db_name]['ENGINE'].split('.')[-1]
            connection = connections[db_name]
            module_name = ['django_evolution.db', engine]
            module = __import__('.'.join(module_name), {}, {}, [''])
            self.evolver = module.EvolutionOperations(database_state,
                                                      connection)
        except ImportError:
            if hasattr(settings, 'DATABASE_ENGINE'):
                module_name = ['django_evolution.db', settings.DATABASE_ENGINE]
                module = __import__('.'.join(module_name), {}, {}, [''])
                self.evolver = module.EvolutionOperations(database_state)
            else:
                raise

    def get_evolver(self):
        return self.evolver

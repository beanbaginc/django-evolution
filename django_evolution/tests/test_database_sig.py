from django.test.testcases import TestCase

from django_evolution.db import EvolutionOperationsMulti
from django_evolution.models import Evolution
from django_evolution.signature import create_database_sig


class DatabaseSigTests(TestCase):
    """Testing database signatures."""
    def setUp(self):
        self.database_sig = create_database_sig('default')
        self.evolver = EvolutionOperationsMulti('default').get_evolver()

    def test_initial_state(self):
        """Testing initial state of database_sig"""
        self.assertEqual(
            set(self.database_sig.keys()),
            set([
                'django_admin_log',
                'auth_permission',
                'auth_group',
                'auth_group_permissions',
                'django_session',
                'auth_user_groups',
                'auth_user_user_permissions',
                'django_site',
                'django_evolution',
                'django_project_version',
                'auth_user',
                'django_content_type',
            ]))

        self.assertTrue('indexes' in self.database_sig['django_evolution'])

        # Check the Evolution model
        index_name = self.evolver.get_index_name(
            Evolution, Evolution._meta.get_field('version'))
        indexes = self.database_sig['django_evolution']['indexes']

        self.assertTrue(index_name in indexes)
        self.assertEqual(
            indexes[index_name],
            {
                'unique': False,
                'columns': ['version_id'],
            })

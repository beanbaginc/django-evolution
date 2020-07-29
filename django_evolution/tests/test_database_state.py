from __future__ import unicode_literals

from django.contrib.auth.models import User
from django.test.testcases import TestCase

from django_evolution.compat.models import get_remote_field
from django_evolution.db.state import DatabaseState, IndexState
from django_evolution.errors import DatabaseStateError
from django_evolution.models import Evolution


class DatabaseStateTests(TestCase):
    """Testing django_evolution.db.state.DatabaseState."""

    def test_initial_state(self):
        """Testing DatabaseState with scan=True"""
        database_state = DatabaseState(db_name='default')

        # Check that a few known tables are in the list, to make sure
        # the scan worked.
        for table_name in ('django_content_type',
                           'django_evolution',
                           'django_project_version'):
            self.assertTrue(database_state.has_table(table_name))

        # Check the Evolution model.
        indexes = [
            (index_state.columns, index_state.unique)
            for index_state in database_state.iter_indexes('django_evolution')
        ]

        self.assertIn((['version_id'], False), indexes)

    def test_clone(self):
        """Testing DatabaseState.clone"""
        database_state = DatabaseState(db_name='default')
        cloned_state = database_state.clone()

        self.assertEqual(cloned_state.db_name, database_state.db_name)
        self.assertEqual(cloned_state._tables, database_state._tables)

    def test_add_table(self):
        """Testing DatabaseState.add_table"""
        database_state = DatabaseState(db_name='default', scan=False)
        database_state.add_table('my_test_table')

        self.assertEqual(database_state._tables['my_test_table'], {
            'indexes': {},
        })

    def test_has_table(self):
        """Testing DatabaseState.has_table"""
        database_state = DatabaseState(db_name='default', scan=False)
        self.assertFalse(database_state.has_table('my_test_table'))

        database_state.add_table('my_test_table')
        self.assertTrue(database_state.has_table('my_test_table'))

    def test_has_model(self):
        """Testing DatabaseState.has_model"""
        database_state = DatabaseState(db_name='default', scan=False)
        self.assertFalse(database_state.has_model(Evolution))

        database_state.rescan_tables()
        self.assertTrue(database_state.has_model(Evolution))

    def test_has_model_with_auto_created(self):
        """Testing DatabaseState.has_model with auto-created model"""
        model = get_remote_field(User._meta.get_field('groups')).through
        self.assertTrue(model._meta.auto_created)

        database_state = DatabaseState(db_name='default', scan=False)
        self.assertFalse(database_state.has_model(model))

        database_state.rescan_tables()
        self.assertTrue(database_state.has_model(model))

    def test_add_index(self):
        """Testing DatabaseState.add_index"""
        database_state = DatabaseState(db_name='default', scan=False)
        database_state.add_table('my_test_table')
        database_state.add_index(table_name='my_test_table',
                                 index_name='my_index',
                                 columns=['col1', 'col2'],
                                 unique=True)

        self.assertEqual(
            database_state._tables['my_test_table']['indexes'],
            {
                'my_index': IndexState(name='my_index',
                                       columns=['col1', 'col2'],
                                       unique=True),
            })

    def test_add_index_with_untracked_table(self):
        """Testing DatabaseState.add_index with untracked table"""
        database_state = DatabaseState(db_name='default', scan=False)

        expected_message = (
            'Unable to add index "my_index" to table "my_test_table". The '
            'table is not being tracked in the database state.'
        )

        with self.assertRaisesMessage(DatabaseStateError, expected_message):
            database_state.add_index(table_name='my_test_table',
                                     index_name='my_index',
                                     columns=['col1', 'col2'],
                                     unique=True)

    def test_add_index_with_existing_index(self):
        """Testing DatabaseState.add_index with existing index"""
        database_state = DatabaseState(db_name='default', scan=False)
        database_state.add_table('my_test_table')
        database_state.add_index(table_name='my_test_table',
                                 index_name='existing_index',
                                 columns=['col1', 'col2'],
                                 unique=True)

        expected_message = (
            'Unable to add index "existing_index" to table "my_test_table". '
            'This index already exists.'
        )

        with self.assertRaisesMessage(DatabaseStateError, expected_message):
            database_state.add_index(table_name='my_test_table',
                                     index_name='existing_index',
                                     columns=['col1', 'col2'],
                                     unique=True)

        # It's fine if it has a new name.
        database_state.add_index(table_name='my_test_table',
                                 index_name='new_index',
                                 columns=['col1', 'col2'],
                                 unique=True)

    def test_remove_index(self):
        """Testing DatabaseState.remove_index"""
        database_state = DatabaseState(db_name='default', scan=False)
        database_state.add_table('my_test_table')
        database_state.add_index(table_name='my_test_table',
                                 index_name='my_index',
                                 columns=['col1', 'col2'],
                                 unique=True)

        database_state.remove_index(table_name='my_test_table',
                                    index_name='my_index',
                                    unique=True)

        self.assertEqual(database_state._tables['my_test_table']['indexes'],
                         {})

    def test_remove_index_with_untracked_table(self):
        """Testing DatabaseState.remove_index with untracked table"""
        database_state = DatabaseState(db_name='default', scan=False)

        expected_message = (
            'Unable to remove index "my_index" from table "my_test_table". '
            'The table is not being tracked in the database state.'
        )

        with self.assertRaisesMessage(DatabaseStateError, expected_message):
            database_state.remove_index(table_name='my_test_table',
                                        index_name='my_index',
                                        unique=True)

    def test_remove_index_with_invalid_index_name(self):
        """Testing DatabaseState.remove_index with invalid index name"""
        database_state = DatabaseState(db_name='default', scan=False)
        database_state.add_table('my_test_table')

        expected_message = (
            'Unable to remove index "my_index" from table "my_test_table". '
            'The index could not be found.'
        )

        with self.assertRaisesMessage(DatabaseStateError, expected_message):
            database_state.remove_index(table_name='my_test_table',
                                        index_name='my_index',
                                        unique=True)

    def test_remove_index_with_invalid_index_type(self):
        """Testing DatabaseState.remove_index with invalid index type"""
        database_state = DatabaseState(db_name='default', scan=False)
        database_state.add_table('my_test_table')
        database_state.add_index(table_name='my_test_table',
                                 index_name='my_index',
                                 columns=['col1', 'col2'],
                                 unique=True)

        expected_message = (
            'Unable to remove index "my_index" from table "my_test_table". '
            'The specified index type (unique=False) does not match the '
            'existing type (unique=True).'
        )

        with self.assertRaisesMessage(DatabaseStateError, expected_message):
            database_state.remove_index(table_name='my_test_table',
                                        index_name='my_index',
                                        unique=False)

    def test_get_index(self):
        """Testing DatabaseState.get_index"""
        database_state = DatabaseState(db_name='default', scan=False)
        database_state.add_table('my_test_table')
        database_state.add_index(table_name='my_test_table',
                                 index_name='my_index',
                                 columns=['col1', 'col2'],
                                 unique=True)

        self.assertEqual(
            database_state.get_index(table_name='my_test_table',
                                     index_name='my_index'),
            IndexState(name='my_index',
                       columns=['col1', 'col2'],
                       unique=True))

    def test_get_index_with_invalid_name(self):
        """Testing DatabaseState.get_index with invalid name"""
        database_state = DatabaseState(db_name='default', scan=False)
        database_state.add_table('my_test_table')

        self.assertIsNone(database_state.get_index(table_name='my_test_table',
                                                   index_name='my_index'),)

    def test_find_index(self):
        """Testing DatabaseState.find_index"""
        database_state = DatabaseState(db_name='default', scan=False)
        database_state.add_table('my_test_table')
        database_state.add_index(table_name='my_test_table',
                                 index_name='my_index',
                                 columns=['col1', 'col2'],
                                 unique=True)

        index = database_state.find_index(table_name='my_test_table',
                                          columns=['col1', 'col2'],
                                          unique=True)
        self.assertEqual(index,
                         IndexState(name='my_index',
                                    columns=['col1', 'col2'],
                                    unique=True))

    def test_find_index_with_not_found(self):
        """Testing DatabaseState.find_index with index no found"""
        database_state = DatabaseState(db_name='default', scan=False)
        database_state.add_table('my_test_table')

        index = database_state.find_index(table_name='my_test_table',
                                          columns=['col1', 'col2'],
                                          unique=True)
        self.assertIsNone(index)

    def clear_indexes(self):
        """Testing DatabaseState.clear_indexes"""
        database_state = DatabaseState(db_name='default', scan=False)
        database_state.add_table('my_test_table')
        database_state.add_index(table_name='my_test_table',
                                 index_name='my_index',
                                 columns=['col1', 'col2'],
                                 unique=True)

        self.assertEqual(database_state._tables['my_test_table']['indexes'],
                         {})

    def test_iter_indexes(self):
        """Testing DatabaseState.iter_indexes"""
        database_state = DatabaseState(db_name='default', scan=False)
        database_state.add_table('my_test_table')
        database_state.add_index(table_name='my_test_table',
                                 index_name='my_index1',
                                 columns=['col1', 'col2'],
                                 unique=True)
        database_state.add_index(table_name='my_test_table',
                                 index_name='my_index2',
                                 columns=['col3'])

        indexes = set(database_state.iter_indexes('my_test_table'))

        self.assertEqual(
            indexes,
            set([
                IndexState(name='my_index1',
                           columns=['col1', 'col2'],
                           unique=True),
                IndexState(name='my_index2',
                           columns=['col3'],
                           unique=False),
            ]))

    def test_rescan_indexes(self):
        """Testing DatabaseState.rescan_indexes"""
        database_state = DatabaseState(db_name='default')

        # Check that a few known tables are in the list, to make sure
        # the scan worked.
        for table_name in ('django_content_type',
                           'django_evolution',
                           'django_project_version'):
            self.assertTrue(database_state.has_table(table_name))

        # Check the Evolution model.
        indexes = [
            (index_state.columns, index_state.unique)
            for index_state in database_state.iter_indexes('django_evolution')
        ]

        self.assertIn((['version_id'], False), indexes)

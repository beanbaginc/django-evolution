import unittest
import copy
import pprint
try:
    import cPickle as pickle
except ImportError:
    import pickle as pickle

from regressiontests.schema_evolution import models as schema_evolution_models
from regressiontests.schema_evolution.evolutions import migration_one

from django.contrib.evolution.models import *
from django.contrib.evolution.mutation import *
from django.db import connection, get_introspection_module
from django.db.models import loading
from django.core.management.commands import syncdb
from django.conf import settings
from django.test.utils import create_test_db, destroy_test_db


class SchemaEvolutionTest(unittest.TestCase):
    
    def install_evolution(self):
        evolution_model_label = 'django.contrib.evolution'
        if not evolution_model_label in settings.INSTALLED_APPS:
            loading.load_app(evolution_model_label)
            try:
                settings.INSTALLED_APPS.index(evolution_model_label)
            except ValueError:
                settings.INSTALLED_APPS.append(evolution_model_label)
            syncdb.Command().handle_noargs(interactive=False)
            
    def delete_test(self, object_name, field_name, field_attributes, expected_sql):
        self.install_evolution()
        from django.contrib.evolution.management import sql_hint

        migration_one.MUTATIONS = [DeleteField(getattr(schema_evolution_models,object_name),field_name)]
        e = Evolution.objects.get(app_name='regressiontests.schema_evolution', version=0)
        original_signature = e.signature
        original_dict = pickle.loads(str(original_signature))
        modified_dict = copy.deepcopy(original_dict)

        # Modify the signature
        modified_dict[object_name][field_name] = field_attributes
        e.signature = pickle.dumps(modified_dict)
        e.save()
        sql_statements = sql_hint('regressiontests.schema_evolution','migration_one')

        # Restore the original state
        e.signature = original_signature
        e.save()
        
        # Assertions
        self.assertEqual(len(expected_sql),len(sql_statements), 'Expected number of sql statements does not match the number of hinted statements.')
        for i in range(0,len(sql_statements)):
            self.assertEqual(expected_sql[i],sql_statements[i])
            
    def test_drop_column(self):
        object_name = 'Person'
        field_name = 'test_field'
        field_attributes = {   'blank': False,
                               'column': field_name,
                               'core': False,
                               'db_column': None,
                               'db_index': False,
                               'db_tablespace': None,
                               'internal_type': 'CharField',
                               'maxlength': 200,
                               'null': False,
                               'primary_key': False,
                               'unique': False}
        expected_sql = ['ALTER TABLE schema_evolution_person DROP COLUMN %s CASCADE;'%field_name]
        self.delete_test(object_name,field_name,field_attributes,expected_sql)    

    def test_drop_table(self):
        object_name = 'Person'
        field_name = 'test_field'
        field_attributes = {   'blank': False,
                               'core': False,
                               'db_column': None,
                               'db_index': False,
                               'db_tablespace': None,
                               'internal_type': 'ManyToManyField',
                               'm2m_db_table': 'schema_evolution_person_%s'%field_name,
                               'maxlength': None,
                               'null': False,
                               'primary_key': False,
                               'unique': False}
        expected_sql = ['DROP TABLE schema_evolution_person_%s;'%field_name]
        self.delete_test(object_name,field_name,field_attributes,expected_sql)
import copy
import re
from itertools import chain

from django.db import models
from django.test.testcases import TransactionTestCase

from django_evolution.diff import Diff
from django_evolution.mutations import ChangeField
from django_evolution.signature import create_database_sig
from django_evolution.tests.utils import (deregister_models,
                                          execute_test_sql,
                                          has_index_with_columns,
                                          register_models,
                                          test_proj_sig,
                                          test_sql_mapping)


class ChangeAnchor1(models.Model):
    value = models.IntegerField()


class BaseModel(models.Model):
    my_id = models.AutoField(primary_key=True)
    alt_pk = models.IntegerField()
    int_field = models.IntegerField(db_column='custom_db_column')
    int_field1 = models.IntegerField(db_index=True)
    int_field2 = models.IntegerField(db_index=False)
    int_field3 = models.IntegerField(unique=True)
    int_field4 = models.IntegerField(unique=False)
    char_field = models.CharField(max_length=20)
    char_field1 = models.CharField(max_length=25, null=True)
    char_field2 = models.CharField(max_length=30, null=False)
    m2m_field1 = models.ManyToManyField(
        ChangeAnchor1,
        db_table='change_field_non-default_m2m_table')


class EvolutionTestCase(TransactionTestCase):
    sql_mapping_key = None

    ws_re = re.compile(r'\s+')

    def setUp(self):
        base_model = self.get_default_base_model()

        if base_model:
            self.set_base_model(base_model)

    def tearDown(self):
        deregister_models()

    def shortDescription(self):
        """Returns the description of the current test.

        This changes the default behavior to replace all newlines with spaces,
        allowing a test description to span lines. It should still be kept
        short, though.
        """
        doc = self._testMethodDoc

        if doc is not None:
            doc = doc.split('\n\n', 1)[0]
            doc = self.ws_re.sub(' ', doc).strip()

        return doc

    def get_default_base_model(self):
        return BaseModel

    def set_base_model(self, model):
        deregister_models()

        self.anchors = [('ChangeAnchor1', ChangeAnchor1)]
        test_model = ('TestModel', model)

        self.database_sig = create_database_sig('default')

        self.start = register_models(self.database_sig,
                                     register_indexes=True,
                                     *self.anchors)
        self.start.update(register_models(
            self.database_sig, test_model, register_indexes=True))
        self.start_sig = test_proj_sig(test_model, *self.anchors)

    def perform_evolution_tests(self, model, evolutions, diff_text,
                                expected_hint, sql_name, expect_noop=False,
                                rescan_indexes=True):
        end = self.register_model(model)
        end_sig = self.create_test_proj_sig(model)

        # See if the diff between signatures contains the contents we expect.
        self.perform_diff_test(end_sig, diff_text, expected_hint,
                               expect_empty=expect_noop)
        self.perform_simulations(evolutions, end_sig)
        self.perform_mutations(evolutions, end, end_sig, sql_name,
                               rescan_indexes=rescan_indexes)

    def perform_diff_test(self, end_sig, diff_text, expected_hint,
                          expect_empty=False):
        d = Diff(self.start_sig, end_sig)
        self.assertEqual(d.is_empty(), expect_empty)

        if not expect_empty:
            self.assertEqual(str(d), diff_text)
            self.assertEqual(
                [str(e) for e in d.evolution()['tests']],
                expected_hint)

    def perform_simulations(self, evolutions, end_sig):
        test_database_sig = self.copy_sig(self.database_sig)
        test_sig = self.copy_sig(self.start_sig)

        for mutation in evolutions:
            mutation.simulate('tests', test_sig, test_database_sig)

        # Check that the simulation's changes results in an empty diff.
        d = Diff(test_sig, end_sig)
        self.assertTrue(d.is_empty())

    def perform_mutations(self, evolutions, end, end_sig, sql_name,
                          rescan_indexes=True):
        test_database_sig = self.copy_sig(self.database_sig)
        test_sig = self.copy_sig(self.start_sig)

        sql = execute_test_sql(
            self.start, end,
            lambda: list(chain.from_iterable([
                mutation.mutate('tests', test_sig, test_database_sig)
                for mutation in evolutions
            ])),
            database_sig=test_database_sig,
            rescan_indexes=rescan_indexes,
            return_sql=True)

        if sql_name is None:
            self.assertEqual(sql, [])
        else:
            self.assertEqual(
                '\n'.join(sql),
                test_sql_mapping(self.sql_mapping_key)[sql_name])

    def register_model(self, model, name='TestModel'):
        return register_models(self.database_sig, (name, model), *self.anchors)

    def create_test_proj_sig(self, model, name='TestModel'):
        return test_proj_sig((name, model), *self.anchors)

    def copy_sig(self, sig):
        return copy.deepcopy(sig)

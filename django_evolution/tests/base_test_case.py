from __future__ import unicode_literals

import copy
import re
from contextlib import contextmanager

from django.db import ConnectionRouter, router
from django.test.testcases import TransactionTestCase
from django.test.utils import override_settings

from django_evolution.compat.apps import unregister_app
from django_evolution.diff import Diff
from django_evolution.mutators import AppMutator
from django_evolution.signature import (create_database_sig,
                                        rescan_indexes_for_database_sig)
from django_evolution.tests.utils import (create_test_project_sig,
                                          execute_test_sql,
                                          get_sql_mappings,
                                          register_models)


class EvolutionTestCase(TransactionTestCase):
    sql_mapping_key = None
    default_database_name = 'default'
    default_model_name = 'TestModel'
    default_base_model = None
    default_pre_extra_models = []
    default_extra_models = []

    ws_re = re.compile(r'\s+')

    # Allow for diffs for large dictionary structures, to help debug
    # signature failures.
    maxDiff = 10000

    def setUp(self):
        self.base_model = None
        self.pre_extra_models = []
        self.extra_models = []
        self.start = None
        self.start_sig = None
        self.database_sig = None
        self.test_database_sig = None
        self._models_registered = False

        if self.default_base_model:
            self.set_base_model(self.default_base_model,
                                pre_extra_models=self.default_pre_extra_models,
                                extra_models=self.default_extra_models)

    def tearDown(self):
        if self._models_registered:
            unregister_app('tests')

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

    def set_base_model(self, model, name=None, extra_models=[],
                       pre_extra_models=[], db_name=None):
        name = name or self.default_model_name
        db_name = db_name or self.default_database_name

        if self.base_model:
            unregister_app('tests')

        self.base_model = model
        self.pre_extra_models = pre_extra_models
        self.extra_models = extra_models
        self.database_sig = create_database_sig(db_name)

        self.start = self.register_model(model, name,
                                         register_indexes=True,
                                         db_name=db_name)
        self.start_sig = self.create_test_proj_sig(model, name)

    def make_end_signatures(self, model, model_name, db_name=None):
        db_name = db_name or self.default_database_name

        end = self.register_model(model, name=model_name, db_name=db_name)
        end_sig = self.create_test_proj_sig(model, name=model_name)

        return end, end_sig

    def perform_evolution_tests(self, model, evolutions, diff_text=None,
                                expected_hint=None, sql_name=None,
                                model_name=None,
                                end=None, end_sig=None,
                                expect_noop=False,
                                rescan_indexes=True,
                                use_hinted_evolutions=False,
                                perform_simulations=True,
                                perform_mutations=True,
                                db_name=None):
        model_name = model_name or self.default_model_name
        db_name = db_name or self.default_database_name

        if end is None or end_sig is None:
            end, end_sig = self.make_end_signatures(model, model_name, db_name)

        # See if the diff between signatures contains the contents we expect.
        d = self.perform_diff_test(end_sig, diff_text, expected_hint,
                                   expect_empty=expect_noop)

        if use_hinted_evolutions:
            assert not evolutions
            evolutions = d.evolution()['tests']

        if perform_simulations:
            self.perform_simulations(evolutions, end_sig, db_name=db_name)

        if perform_mutations:
            self.perform_mutations(evolutions, end, end_sig, sql_name,
                                   rescan_indexes=rescan_indexes,
                                   db_name=db_name)

    def perform_diff_test(self, end_sig, diff_text, expected_hint,
                          expect_empty=False):
        d = Diff(self.start_sig, end_sig)
        self.assertEqual(d.is_empty(), expect_empty)

        if not expect_empty:
            if diff_text is not None:
                self.assertEqual(str(d), diff_text)

            if expected_hint is not None:
                self.assertEqual(
                    [str(e) for e in d.evolution()['tests']],
                    expected_hint)

        return d

    def perform_simulations(self, evolutions, end_sig, ignore_apps=False,
                            db_name=None):
        db_name = db_name or self.default_database_name

        self.test_database_sig = self.copy_sig(self.database_sig)
        test_sig = self.copy_sig(self.start_sig)

        for mutation in evolutions:
            mutation.run_simulation(app_label='tests',
                                    project_sig=test_sig,
                                    database_sig=self.test_database_sig,
                                    database=db_name)

        # Check that the simulation's changes results in an empty diff.
        d = Diff(test_sig, end_sig)
        self.assertTrue(d.is_empty(ignore_apps=ignore_apps))

    def perform_mutations(self, evolutions, end, end_sig, sql_name,
                          rescan_indexes=True, db_name=None):
        def run_mutations():
            if rescan_indexes:
                rescan_indexes_for_database_sig(self.test_database_sig,
                                                db_name)

            app_mutator = AppMutator('tests', test_sig, self.test_database_sig,
                                     db_name)
            app_mutator.run_mutations(evolutions)

            return app_mutator.to_sql()

        db_name = db_name or self.default_database_name

        self.test_database_sig = self.copy_sig(self.database_sig)
        test_sig = self.copy_sig(self.start_sig)

        sql = execute_test_sql(self.start, end, run_mutations,
                               database=db_name)

        if sql_name is not None:
            # Normalize the generated and expected SQL so that we are
            # guaranteed to have a list with one item per line.
            generated_sql = '\n'.join(sql).splitlines()
            expected_sql = self.get_sql_mapping(sql_name, db_name).splitlines()

            # Output the statements one-by-one, to help with diagnosing
            # differences.

            print
            print "** Comparing SQL against '%s.%s'" % (self.sql_mapping_key,
                                                        sql_name)
            print '** Generated:'
            print

            for line in generated_sql:
                print '    %s' % line

            print
            print '** Expected:'
            print

            for line in expected_sql:
                print '    %s' % line

            print

            # Compare as lists, so that we can better spot inconsistencies.
            self.assertListEqual(generated_sql, expected_sql)

    def get_sql_mapping(self, name, db_name=None):
        db_name = db_name or self.default_database_name

        return get_sql_mappings(self.sql_mapping_key, db_name)[name]

    def register_model(self, model, name, db_name=None, **kwargs):
        self._models_registered = True

        models = self.pre_extra_models + [(name, model)] + self.extra_models

        return register_models(database_sig=self.database_sig,
                               models=models,
                               new_app_label='tests',
                               db_name=db_name or self.default_database_name,
                               **kwargs)

    def create_test_proj_sig(self, model, name, extra_models=[],
                             pre_extra_models=[]):
        return create_test_project_sig(models=(
            self.pre_extra_models + pre_extra_models + [(name, model)] +
            extra_models + self.extra_models
        ))

    def copy_sig(self, sig):
        return copy.deepcopy(sig)

    def copy_models(self, models):
        return copy.deepcopy(models)

    @contextmanager
    def override_db_routers(self, routers):
        """Override database routers for a test.

        This clears the router cache before and after the test, allowing
        custom routers to be used during unit tests.

        Args:
            routers (list):
                The list of router class paths or instances.

        Yields:
            The context.
        """
        with override_settings(DATABASE_ROUTERS=routers):
            self.clear_routers_cache()
            yield

        self.clear_routers_cache()

    def clear_routers_cache(self):
        """Clear the router cache."""
        router.routers = ConnectionRouter().routers

from __future__ import print_function, unicode_literals

import copy
import re
from contextlib import contextmanager

from django.db import ConnectionRouter, DEFAULT_DB_ALIAS, connections, router
from django.test.testcases import TransactionTestCase
from django.test.utils import override_settings

from django_evolution.compat import six
from django_evolution.compat.apps import unregister_app
from django_evolution.db.state import DatabaseState
from django_evolution.diff import Diff
from django_evolution.mutators import AppMutator
from django_evolution.support import supports_migrations
from django_evolution.tests.utils import (create_test_project_sig,
                                          execute_test_sql,
                                          get_sql_mappings,
                                          register_models)
from django_evolution.utils.migrations import unrecord_applied_migrations


class TestCase(TransactionTestCase):
    """Base class for all Django Evolution test cases."""

    ws_re = re.compile(r'\s+')

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


class MigrationsTestsMixin(object):
    """Mixin for test suites that work with migrations.

    This will ensure that no test migrations are marked as applied before
    the tests run.
    """

    def setUp(self):
        super(MigrationsTestsMixin, self).setUp()

        if supports_migrations:
            unrecord_applied_migrations(
                connection=connections[DEFAULT_DB_ALIAS],
                app_label='tests')


class EvolutionTestCase(TestCase):
    """Base class for test cases that need to evolve the database."""

    sql_mapping_key = None
    default_database_name = 'default'
    default_model_name = 'TestModel'
    default_base_model = None
    default_pre_extra_models = []
    default_extra_models = []

    # Allow for diffs for large dictionary structures, to help debug
    # signature failures.
    maxDiff = 10000

    # The list of databases we may test against, required by Django 2.2+.
    databases = ['default', 'db_multi']

    def setUp(self):
        self.base_model = None
        self.pre_extra_models = []
        self.extra_models = []
        self.start = None
        self.start_sig = None
        self.database_state = None
        self.test_database_state = None
        self._models_registered = False

        if self.default_base_model:
            self.set_base_model(base_model=self.default_base_model,
                                pre_extra_models=self.default_pre_extra_models,
                                extra_models=self.default_extra_models)

    def tearDown(self):
        if self._models_registered:
            unregister_app('tests')

    def set_base_model(self, base_model, name=None, extra_models=[],
                       pre_extra_models=[], db_name=None):
        """Set the base model(s) that will be mutated in a test.

        These models will be registered in Django's model registry and
        queued up to be written to the database. Starting signatures based
        on these models will be provided, which the test is expected to
        mutate.

        Args:
            base_model (type):
                The base :py:class:`~django.db.models.Model` to register and
                write to the database that the test will then mutate.

            name (unicode, optional):
                The name to register for the model. This defaults to
                :py:attr:`default_model_name`.

            extra_models (list of type, optional):
                The list of extra models to register and write to the
                database after writing ``base_model``. These may form
                relations to ``base_model``.

            pre_extra_models (list of type, optional):
                The list of extra models to write to the database before
                writing ``base_model``. ``base_model`` may form relations to
                these models.

            db_name (unicode, optional):
                The name of the database to write the models to. This
                defaults to :py:attr:`default_database_name`.
        """
        name = name or self.default_model_name
        db_name = db_name or self.default_database_name

        if self.base_model:
            unregister_app('tests')

        self.base_model = base_model
        self.pre_extra_models = pre_extra_models
        self.extra_models = extra_models
        self.database_state = DatabaseState(db_name)

        self.start = self.register_model(model=base_model,
                                         name=name,
                                         register_indexes=True,
                                         db_name=db_name)
        self.start_sig = self.create_test_proj_sig(model=base_model,
                                                   name=name)

    def make_end_signatures(self, dest_model, model_name, db_name=None):
        """Return signatures for a model representing the end of a mutation.

        Callers should construct a model that reflects the expected result
        of any mutations and provide that. This will register that model
        and construct a signature from it.

        Args:
            dest_model (type):
                The destination :py:class:`~django.db.models.Model`
                representing the expected result of an evolution.

            model_name (unicode):
                The name to register for the model.

            db_name (unicode, optional):
                The name of the database to write the models to. This
                defaults to :py:attr:`default_database_name`.

        Returns:
            tuple:
            A tuple containing:

            1. A :py:class:`collections.OrderedDict` mapping the model name
               to the model class.
            2. A :py:class:`django_evolution.signature.ProjectSignature`
               for the provided model.
        """
        db_name = db_name or self.default_database_name

        end = self.register_model(model=dest_model,
                                  name=model_name,
                                  db_name=db_name)
        end_sig = self.create_test_proj_sig(model=dest_model,
                                            name=model_name)

        return end, end_sig

    def perform_evolution_tests(self,
                                dest_model,
                                evolutions,
                                diff_text=None,
                                expected_hint=None,
                                sql_name=None,
                                model_name=None,
                                end=None,
                                end_sig=None,
                                expect_noop=False,
                                rescan_indexes=True,
                                use_hinted_evolutions=False,
                                perform_simulations=True,
                                perform_mutations=True,
                                db_name=None):
        """Perform test evolutions and validate results.

        This is used for most common evolution-related tests. It handles
        generating signatures for a base model and an expected post-evolution
        model, ensuring that the mutations result in an empty diff.

        It then optionally simulates the evolutions on the signatures
        (using :py:meth:`perform_simulations)`, and then optionally performs
        the actual evolutions on the database (using
        :py:meth:`perform_mutations`), verifying all results.

        Args:
            dest_model (type):
                The destination :py:class:`~django.db.models.Model`
                representing the expected result of an evolution.

            evolutions (list of django_evolution.mutations.BaseMutation):
                The combined series of evolutions (list of mutations) to apply
                to the base model.

            diff_text (unicode, optional):
                The expected generated text describing a diff that must
                match, if provided.

            expected_hint (unicode, optional):
                The expected generated hint text that must match, if provided.

            sql_name (unicode, optional):
                The name of the registered SQL content for the database being
                tested.

                This must be provided if ``perform_mutations`` is ``True`.

            model_name (unicode, optional):
                The name of the model to register. This defaults to
                :py:attr:`default_model_name`.

            end (collections.OrderedDict, optional):
                The expected model map at the end of the evolution. This
                is generated by :py:meth:`make_end_signatures`.

                If not provided, one will be generated.

            end_sig (django_evolution.signature.ProjectSignature, optional):
                The expected project signature at the end of the evolution.
                This is generated by :py:meth:`make_end_signatures`.

                If not provided, one will be generated.

            expect_noop (bool, optional):
                Whether the evolution is expected not to change anything.

            rescan_indexes (bool, optional):
                Whether to re-scan the list of table indexes after performing
                mutations.

                This is ignored if ``perform_mutations`` is ``False``.

            use_hinted_evolutions (bool, optional):
                Whether to use the hinted evolutions generated by the
                signatures. This cannot be used if ``evolutions`` is
                non-empty.

            perform_simulations (bool, optional):
                Whether to simulate the evolution and compare results.

            perform_mutations (bool, optional):
                Whether to apply the mutations and compare results.

            db_name (unicode, optional):
                The name of the database to apply evolutions to. This
                defaults to :py:attr:`default_database_name`.

        Raises:
            AssertionError:
                A diff, simulation, or mutation test has failed.
        """
        model_name = model_name or self.default_model_name
        db_name = db_name or self.default_database_name

        if end is None or end_sig is None:
            end, end_sig = self.make_end_signatures(dest_model=dest_model,
                                                    model_name=model_name,
                                                    db_name=db_name)

        # See if the diff between signatures contains the contents we expect.
        d = self.perform_diff_test(end_sig=end_sig,
                                   diff_text=diff_text,
                                   expected_hint=expected_hint,
                                   expect_empty=expect_noop)

        if use_hinted_evolutions:
            assert not evolutions, (
                'The evolutions= argument cannot be provided when providing '
                'use_hinted_evolutions=True'
            )

            evolutions = d.evolution()['tests']

        if perform_simulations:
            self.perform_simulations(evolutions=evolutions,
                                     end_sig=end_sig,
                                     db_name=db_name)

        if perform_mutations:
            self.perform_mutations(evolutions=evolutions,
                                   end=end,
                                   end_sig=end_sig,
                                   sql_name=sql_name,
                                   rescan_indexes=rescan_indexes,
                                   db_name=db_name)

    def perform_diff_test(self, end_sig, diff_text=None, expected_hint=None,
                          expect_empty=False):
        """Generate a diff between signatures and check for expected results.

        The registered base signature and the provided ending signature will
        be diffed, asserted to be empty/not empty (depending on the arguments),
        and then checked against the provided diff text and hint.

        Args:
            end_sig (django_evolution.signature.ProjectSignature):
                The expected project signature at the end of the evolution.
                This is generated by :py:meth:`make_end_signatures`.

            diff_text (unicode, optional):
                The expected generated text describing a diff that must
                match, if provided.

            expected_hint (unicode, optional):
                The expected generated hint text that must match, if provided.

            expect_empty (bool, optional):
                Whether the diff is expected to be empty.

        Returns:
            django_evolution.diff.Diff:
            The resulting diff.

        Raises:
            AssertionError:
                One of the expectations has failed.
        """
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
        """Run simulations and verify that they result in an end signature.

        This will run through an evolution chain, simulating each one on a
        copy of the starting signature, and then verifying that the signature
        is properly transformed into the expected ending signature.

        Args:
            evolutions (list of django_evolution.mutations.BaseMutation):
                The evolution chain to run simulations on.

            end_sig (django_evolution.signature.ProjectSignature):
                The expected ending signature.

            ignore_apps (bool, optional):
                Whether to ignore changes to the list of applications.

            db_name (unicode, optional):
                The name of the database to perform the simulations against.

        Returns:
            django_evolution.signature.ProjectSignature:
            The resulting modified signature.

        Raises:
            AssertionError:
                The modified signature did not match the expected end
                signature.
        """
        db_name = db_name or self.default_database_name

        self.test_database_state = self.database_state.clone()
        test_sig = self.start_sig.clone()

        for mutation in evolutions:
            mutation.run_simulation(app_label='tests',
                                    project_sig=test_sig,
                                    database_state=self.test_database_state,
                                    database=db_name)

        # Check that the simulation's changes results in an empty diff.
        d = Diff(test_sig, end_sig)
        self.assertTrue(d.is_empty(ignore_apps=ignore_apps))

        return test_sig

    def perform_mutations(self, evolutions, end, end_sig, sql_name=None,
                          rescan_indexes=True, db_name=None):
        """Apply mutations that and verify the results.

        This will run through the evolution chain, applying each mutation
        on the database and against the signature, and then verifying the
        resulting signature and generated SQL.

        Args:
            evolutions (list of django_evolution.mutations.BaseMutation):
                The evolution chain to run simulations on.

            end (collections.OrderedDict):
                The expected model map at the end of the evolution. This
                is generated by :py:meth:`make_end_signatures`.

            end_sig (django_evolution.signature.ProjectSignature):
                The expected ending signature. This is generated by
                :py:meth:`make_end_signatures`.

            sql_name (unicode, optional):
                The name of the registered SQL content for the database being
                tested. If not provided, the SQL won't be compared.

            rescan_indexes (bool, optional):
                Whether to re-scan the list of table indexes after applying
                the mutations.

            db_name (unicode, optional):
                The name of the database to apply the evolutions against.

        Raises:
            AssertionError:
                The resulting SQL did not match.

            django.db.utils.OperationalError:
                There was an error executing SQL.
        """
        def run_mutations():
            if rescan_indexes:
                self.test_database_state.rescan_tables()

            app_mutator = AppMutator(app_label='tests',
                                     project_sig=test_sig,
                                     database_state=self.test_database_state,
                                     database=db_name)
            app_mutator.run_mutations(evolutions)

            return app_mutator.to_sql()

        db_name = db_name or self.default_database_name

        self.test_database_state = self.database_state.clone()
        test_sig = self.start_sig.clone()

        sql = execute_test_sql(start_models=self.start,
                               end_models=end,
                               generate_sql_func=run_mutations,
                               database=db_name)

        if sql_name is not None:
            self.assertSQLMappingEqual(sql, sql_name, db_name)

    def get_sql_mapping(self, name, db_name=None):
        """Return the SQL for the given mapping name and database.

        Args:
            name (unicode):
                The registered name in the list of SQL mappings for this test
                suite and database.

            db_name (unicode, optional):
                The name of the database to return SQL mappings for.

        Returns:
            list of unicode:
            The resulting list of SQL statements.

        Raises:
            ValueError:
                The provided name is not valid.
        """
        db_name = db_name or self.default_database_name
        sql_mappings = get_sql_mappings(mapping_key=self.sql_mapping_key,
                                        db_name=db_name)

        try:
            sql = sql_mappings[name]
        except KeyError:
            raise ValueError('"%s" is not a valid SQL mapping name.'
                             % name)

        if isinstance(sql, six.text_type):
            sql = sql.splitlines()

        return sql

    def assertSQLMappingEqual(self, sql, sql_mapping_name, db_name=None):
        """Assert generated SQL against database-specific mapped test SQL.

        This will output the provided generated SQL and the expectation test
        SQL mapped by the given key and optional database name, for debugging,
        and will then compare the contents of both.

        The expected SQL may contain regexes, which are used for comparing
        against generated SQL that may depend on some dynamic value pulled from
        the database). If found, the pattern in the regex will be applied to
        the corresponding generated SQL to determine if there's a match. Other
        lines will be compared directly.

        If any part of the SQL does not match, a diff will be shown in the
        test output.

        Args:
            sql (list of unicode):
                The list of generated SQL statements.

            sql_mapping_name (unicode):
                The mapping name in the database-specific test data to compare
                against.

            db_name (unicode, optional):
                An explicit database name to use for resolving
                ``sql_mapping_name``.

        Raises:
            AssertionError:
                The generated and expected SQL did not match.
        """
        # Normalize the generated and expected SQL so that we are
        # guaranteed to have a list with one item per line.
        generated_sql = '\n'.join(sql).splitlines()
        expected_sql = self.get_sql_mapping(name=sql_mapping_name,
                                            db_name=db_name)

        # Output the statements one-by-one, to help with diagnosing
        # differences.

        print()
        print("** Comparing SQL against '%s'" % sql_mapping_name)
        print('** Generated:')
        print()

        for line in generated_sql:
            print('    %s' % line)

        print()
        print('** Expected:')
        print()

        has_regex = False

        for line in expected_sql:
            if (not isinstance(line, six.text_type) and
                hasattr(line, 'pattern')):
                line = '/%s/' % line.pattern
                has_regex = True

            print('    %s' % line)

        print()

        if has_regex:
            # We can't compare directly at first, so let's see if things
            # are otherwise a match and then, if we spot anything wrong,
            # we'll just do an assertListEqual to get detailed output.
            match = (len(generated_sql) == len(expected_sql))

            if match:
                for gen_line, expected_line in zip(generated_sql,
                                                   expected_sql):
                    if ((isinstance(expected_line, six.text_type) and
                         gen_line != expected_line) or
                        (hasattr(line, 'pattern') and
                         not line.match(gen_line))):
                        match = False
                        break

            if not match:
                # Now show that detailed output.
                self.assertListEqual(generated_sql, expected_sql)
        else:
            # Compare as lists, so that we can better spot inconsistencies.
            self.assertListEqual(generated_sql, expected_sql)

    def register_model(self, model, name, db_name=None, **kwargs):
        """Register a model for the test.

        This will register not only this model, but any models in
        :py:attr:`pre_extra_models` and :py:attr:`extra_models`. It will
        not include :py:attr:`base_model`.

        Args:
            model (type):
                The main :py:class:`~django.db.models.Model` to register.

            name (unicode):
                The name to use when for the model when registering. This
                doesn't have to match the model's actual name.

            db_name (unicode, optional):
                The name of the database to register this model on.

            **kwargs (dict):
                Additional keyword arguments to pass to
                :py:func:`~django_evolution.tests.utils.register_models`.

        Returns:
            collections.OrderedDict:
            A dictionary of registered models. The keys are model names, and
            the values are the models.
        """
        self._models_registered = True

        models = self.pre_extra_models + [(name, model)] + self.extra_models

        return register_models(database_state=self.database_state,
                               models=models,
                               new_app_label='tests',
                               db_name=db_name or self.default_database_name,
                               **kwargs)

    def create_test_proj_sig(self, model, name, extra_models=[],
                             pre_extra_models=[]):
        """Create a project signature for the given models.

        The signature will include not only these models, but any models in
        :py:attr:`pre_extra_models` and :py:attr:`extra_models`. It will
        not include :py:attr:`base_model`.

        Args:
            model (type):
                The main :py:class:`~django.db.models.Model` to include
                in the signature.

            name (unicode):
                The name to use when for the model. This doesn't have to match
                the model's actual name.

            extra_models (list of type, optional):
                An additional list of extra models to register after ``model``
                (but before the class-defined :py:attr:`extra_models`).

            pre_extra_models (list of type, optional):
                An additional list of extra models to register before ``model``
                (but after :py:attr:`pre_extra_models`).

        Returns:
            django_evolution.signature.ProjectSignature:
            The generated project signature.
        """
        return create_test_project_sig(models=(
            self.pre_extra_models + pre_extra_models + [(name, model)] +
            extra_models + self.extra_models
        ))

    def copy_models(self, models):
        """Copy a list of models.

        This will be a deep copy, allowing any of the copied models to be
        altered without affecting the originals.

        Args:
            models (list of type):
                The list of :py:class:`~django.db.models.Model` classes.

        Returns:
            list of type:
            The copied list of :py:class:`~django.db.models.Model` classes.
        """
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
        try:
            with override_settings(DATABASE_ROUTERS=routers):
                self.clear_routers_cache()
                yield
        finally:
            self.clear_routers_cache()

    def clear_routers_cache(self):
        """Clear the router cache."""
        router.routers = ConnectionRouter().routers

"""Unit tests for django_evolution.mutators.ModelMutator."""

from __future__ import unicode_literals

from django.db import models

from django_evolution.errors import EvolutionBaselineMissingError
from django_evolution.mutators import AppMutator, ModelMutator
from django_evolution.tests.base_test_case import EvolutionTestCase
from django_evolution.tests.models import BaseTestModel


class ModelMutatorTestModel(BaseTestModel):
    value = models.CharField(max_length=100)


class ModelMutatorTests(EvolutionTestCase):
    """Unit tests for django_evolution.mutators.ModelMutator."""

    default_base_model = ModelMutatorTestModel

    def setUp(self):
        super(ModelMutatorTests, self).setUp()

        database_state = self.database_state
        project_sig = self.start_sig
        app_mutator = AppMutator(app_label='tests',
                                 project_sig=project_sig,
                                 database_state=database_state,
                                 database=self.default_database_name)
        self.model_mutator = ModelMutator(app_mutator=app_mutator,
                                          model_name=self.default_model_name,
                                          app_label='tests',
                                          legacy_app_label='old_tests',
                                          project_sig=project_sig,
                                          database_state=database_state)

        self.app_sig = self.start_sig.get_app_sig('tests')
        self.model_sig = self.app_sig.get_model_sig(self.default_model_name)

    def test_model_sig(self):
        """Testing ModelMutator.model_sig"""
        self.assertIs(self.model_mutator.model_sig,
                      self.model_sig)

    def test_model_sig_with_legacy_app_label(self):
        """Testing ModelMutator.model_sig with legacy app label"""
        self.start_sig.remove_app_sig('tests')
        self.app_sig.app_id = 'old_tests'
        self.start_sig.add_app_sig(self.app_sig)

        self.assertIs(self.model_mutator.model_sig,
                      self.model_sig)

    def test_model_sig_with_missing_app_sig(self):
        """Testing ModelMutator.model_sig with missing app signature"""
        self.start_sig.remove_app_sig('tests')

        message = 'The app signature for "tests" could not be found.'

        with self.assertRaisesMessage(EvolutionBaselineMissingError, message):
            self.model_mutator.model_sig

    def test_model_sig_with_missing_model_sig(self):
        """Testing ModelMutator.model_sig with missing model signature"""
        self.start_sig.get_app_sig('tests').remove_model_sig('TestModel')

        message = \
            'The model signature for "tests.TestModel" could not be found.'

        with self.assertRaisesMessage(EvolutionBaselineMissingError, message):
            self.model_mutator.model_sig

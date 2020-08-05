from __future__ import unicode_literals

from django.db import models

from django_evolution.errors import CannotSimulate
from django_evolution.mutations import SQLMutation
from django_evolution.signature import FieldSignature, ProjectSignature
from django_evolution.tests.base_test_case import EvolutionTestCase
from django_evolution.tests.models import BaseTestModel


class SQLBaseModel(BaseTestModel):
    char_field = models.CharField(max_length=20)
    int_field = models.IntegerField()


class AddFieldsModel(BaseTestModel):
    char_field = models.CharField(max_length=20)
    int_field = models.IntegerField()
    added_field1 = models.IntegerField(null=True)
    added_field2 = models.IntegerField(null=True)
    added_field3 = models.IntegerField(null=True)


class SQLMutationTests(EvolutionTestCase):
    """Testing ordering of operations."""
    sql_mapping_key = 'sql_mutation'
    default_base_model = SQLBaseModel

    def test_add_fields_no_update_func(self):
        """Testing SQLMutation and no update_func provided"""
        mutation = SQLMutation('test', '')

        message = (
            'SQLMutations must provide an update_func(simulation) or '
            'legacy update_func(app_label, project_sig) parameter in '
            'order to be simulated.'
        )

        with self.assertRaisesMessage(CannotSimulate, message):
            mutation.run_simulation(app_label='tests',
                                    project_sig=ProjectSignature(),
                                    database_state=None)

    def test_add_fields_bad_update_func_signature(self):
        """Testing SQLMutation and bad update_func signature"""
        mutation = SQLMutation('test', '', update_func=lambda a, b, c: None)

        message = (
            'SQLMutations must provide an update_func(simulation) or '
            'legacy update_func(app_label, project_sig) parameter in '
            'order to be simulated.'
        )

        with self.assertRaisesMessage(CannotSimulate, message):
            mutation.run_simulation(app_label='tests',
                                    project_sig=ProjectSignature(),
                                    database_state=None)

    def test_add_fields_simulation_functions(self):
        """Testing SQLMutation and adding fields with simulation functions"""
        # Legacy simulation function.
        def update_first_two(app_label, proj_sig):
            app_sig = proj_sig[app_label]
            model_sig = app_sig['TestModel']
            model_sig['fields']['added_field1'] = {
                'field_type': models.IntegerField,
                'null': True
            }
            model_sig['fields']['added_field2'] = {
                'field_type': models.IntegerField,
                'null': True
            }

        # Modern simulation function.
        def update_third(simulation):
            model_sig = simulation.get_model_sig('TestModel')
            model_sig.add_field_sig(FieldSignature(
                field_name='added_field3',
                field_type=models.IntegerField,
                field_attrs={
                    'null': True,
                }))

        self.perform_evolution_tests(
            AddFieldsModel,
            [
                SQLMutation(
                    'first-two-fields',
                    self.get_sql_mapping('AddFirstTwoFields'),
                    update_first_two),
                SQLMutation(
                    'third-field',
                    self.get_sql_mapping('AddThirdField'),
                    update_third),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'added_field1' has been added\n"
             "    Field 'added_field2' has been added\n"
             "    Field 'added_field3' has been added"),
            sql_name='SQLMutationOutput')

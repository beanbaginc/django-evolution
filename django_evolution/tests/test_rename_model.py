from __future__ import unicode_literals

from django.db import models

from django_evolution.errors import SimulationFailure
from django_evolution.mutations import RenameModel
from django_evolution.signature import AppSignature, ProjectSignature
from django_evolution.tests.base_test_case import EvolutionTestCase
from django_evolution.tests.models import BaseTestModel


class RenameModelBaseModel(BaseTestModel):
    char_field = models.CharField(max_length=20)
    int_field = models.IntegerField()


class RenameModelTests(EvolutionTestCase):
    """Unit tests for RenameModel mutations."""
    sql_mapping_key = 'rename_model'
    default_base_model = RenameModelBaseModel

    def test_with_bad_app(self):
        """Testing RenameModel with application not in signature"""
        mutation = RenameModel('TestModel', 'DestModel',
                               db_table='tests_destmodel')

        message = (
            'Cannot rename the model "badapp.TestModel". The application '
            'could not be found in the signature.'
        )

        with self.assertRaisesMessage(SimulationFailure, message):
            mutation.run_simulation(app_label='badapp',
                                    project_sig=ProjectSignature(),
                                    database_state=None)

    def test_with_bad_model(self):
        """Testing RenameModel with model not in signature"""
        mutation = RenameModel('TestModel', 'DestModel',
                               db_table='tests_destmodel')

        project_sig = ProjectSignature()
        project_sig.add_app_sig(AppSignature(app_id='tests'))

        message = (
            'Cannot rename the model "tests.TestModel". The model could '
            'not be found in the signature.'
        )

        with self.assertRaisesMessage(SimulationFailure, message):
            mutation.run_simulation(app_label='tests',
                                    project_sig=project_sig,
                                    database_state=None)

    def test_rename(self):
        """Testing RenameModel with changed db_table"""
        class DestModel(BaseTestModel):
            char_field = models.CharField(max_length=20)
            int_field = models.IntegerField()

        self.perform_evolution_tests(
            DestModel,
            [
                RenameModel('TestModel', 'DestModel',
                            db_table='tests_destmodel'),
            ],
            "The model tests.TestModel has been deleted",
            [
                "DeleteModel('TestModel')",
            ],
            'RenameModel',
            model_name='DestModel')

    def test_rename_unchanged_db_table(self):
        """Testing RenameModel with unchanged db_table"""
        class DestModel(BaseTestModel):
            char_field = models.CharField(max_length=20)
            int_field = models.IntegerField()

            class Meta(BaseTestModel.Meta):
                db_table = 'tests_testmodel'

        self.perform_evolution_tests(
            DestModel,
            [
                RenameModel('TestModel', 'DestModel',
                            db_table='tests_testmodel'),
            ],
            "The model tests.TestModel has been deleted",
            [
                "DeleteModel('TestModel')",
            ],
            'RenameModelSameTable',
            model_name='DestModel')

    def test_rename_updates_foreign_key_refs(self):
        """Testing RenameModel updates ForeignKey references in signature"""
        class DestModel(BaseTestModel):
            char_field = models.CharField(max_length=20)
            int_field = models.IntegerField()

        class RefModel(BaseTestModel):
            my_ref = models.ForeignKey(RenameModelBaseModel,
                                       on_delete=models.CASCADE)

        self.set_base_model(self.default_base_model,
                            pre_extra_models=[('RefModel', RefModel)])

        end, end_sig = self.make_end_signatures(DestModel, 'DestModel')

        end_field_sig = (
            end_sig
            .get_app_sig('tests')
            .get_model_sig('RefModel')
            .get_field_sig('my_ref')
        )
        end_field_sig.related_model = 'tests.DestModel'

        self.perform_evolution_tests(
            DestModel,
            [
                RenameModel('TestModel', 'DestModel',
                            db_table='tests_destmodel'),
            ],
            ("The model tests.TestModel has been deleted\n"
             "In model tests.RefModel:\n"
             "    In field 'my_ref':\n"
             "        Property 'related_model' has changed"),
            [
                "ChangeField('RefModel', 'my_ref', initial=None,"
                " related_model='tests.DestModel')",
                "DeleteModel('TestModel')",
            ],
            'RenameModelForeignKeys',
            end=end,
            end_sig=end_sig)

    def test_rename_updates_foreign_key_refs_unchanged_db_table(self):
        """Testing RenameModel updates ForeignKey references in signature
        and unchanged db_table
        """
        class DestModel(BaseTestModel):
            char_field = models.CharField(max_length=20)
            int_field = models.IntegerField()

            class Meta(BaseTestModel.Meta):
                db_table = 'tests_testmodel'

        class RefModel(BaseTestModel):
            my_ref = models.ForeignKey(RenameModelBaseModel,
                                       on_delete=models.CASCADE)

        self.set_base_model(self.default_base_model,
                            pre_extra_models=[('RefModel', RefModel)])

        end, end_sig = self.make_end_signatures(DestModel, 'DestModel')
        end_field_sig = (
            end_sig
            .get_app_sig('tests')
            .get_model_sig('RefModel')
            .get_field_sig('my_ref')
        )
        end_field_sig.related_model = 'tests.DestModel'

        self.perform_evolution_tests(
            DestModel,
            [
                RenameModel('TestModel', 'DestModel',
                            db_table='tests_testmodel'),
            ],
            ("The model tests.TestModel has been deleted\n"
             "In model tests.RefModel:\n"
             "    In field 'my_ref':\n"
             "        Property 'related_model' has changed"),
            [
                "ChangeField('RefModel', 'my_ref', initial=None,"
                " related_model='tests.DestModel')",
                "DeleteModel('TestModel')",
            ],
            'RenameModelForeignKeysSameTable',
            end=end,
            end_sig=end_sig)

    def test_rename_updates_m2m_refs(self):
        """Testing RenameModel updates ManyToManyField references in
        signature and changed db_table
        """
        class DestModel(BaseTestModel):
            char_field = models.CharField(max_length=20)
            int_field = models.IntegerField()

        class RefModel(BaseTestModel):
            my_ref = models.ManyToManyField(RenameModelBaseModel)

        self.set_base_model(self.default_base_model,
                            pre_extra_models=[('RefModel', RefModel)])

        end, end_sig = self.make_end_signatures(DestModel, 'DestModel')

        end_field_sig = (
            end_sig
            .get_app_sig('tests')
            .get_model_sig('RefModel')
            .get_field_sig('my_ref')
        )
        end_field_sig.related_model = 'tests.DestModel'

        self.perform_evolution_tests(
            DestModel,
            [
                RenameModel('TestModel', 'DestModel',
                            db_table='tests_destmodel'),
            ],
            ("The model tests.TestModel has been deleted\n"
             "In model tests.RefModel:\n"
             "    In field 'my_ref':\n"
             "        Property 'related_model' has changed"),
            [
                "ChangeField('RefModel', 'my_ref', initial=None,"
                " related_model='tests.DestModel')",
                "DeleteModel('TestModel')",
            ],
            'RenameModelManyToManyField',
            end=end,
            end_sig=end_sig)

    def test_rename_updates_m2m_refs_unchanged_db_table(self):
        """Testing RenameModel updates ManyToManyField references in
        signature and unchanged db_table
        """
        class DestModel(BaseTestModel):
            char_field = models.CharField(max_length=20)
            int_field = models.IntegerField()

            class Meta(BaseTestModel.Meta):
                db_table = 'tests_testmodel'

        class RefModel(BaseTestModel):
            my_ref = models.ManyToManyField(RenameModelBaseModel)

        self.set_base_model(self.default_base_model,
                            pre_extra_models=[('RefModel', RefModel)])

        end, end_sig = self.make_end_signatures(DestModel, 'DestModel')

        end_field_sig = (
            end_sig
            .get_app_sig('tests')
            .get_model_sig('RefModel')
            .get_field_sig('my_ref')
        )
        end_field_sig.related_model = 'tests.DestModel'

        self.perform_evolution_tests(
            DestModel,
            [
                RenameModel('TestModel', 'DestModel',
                            db_table='tests_testmodel'),
            ],
            ("The model tests.TestModel has been deleted\n"
             "In model tests.RefModel:\n"
             "    In field 'my_ref':\n"
             "        Property 'related_model' has changed"),
            [
                "ChangeField('RefModel', 'my_ref', initial=None,"
                " related_model='tests.DestModel')",
                "DeleteModel('TestModel')",
            ],
            'RenameModelManyToManyFieldSameTable',
            end=end,
            end_sig=end_sig)

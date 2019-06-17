from __future__ import unicode_literals

from django.db import models

from django_evolution.errors import SimulationFailure
from django_evolution.mutations import DeleteField
from django_evolution.signature import (AppSignature,
                                        ModelSignature,
                                        ProjectSignature)
from django_evolution.tests.base_test_case import EvolutionTestCase
from django_evolution.tests.models import BaseTestModel


class DeleteAnchor1(BaseTestModel):
    value = models.IntegerField()


class DeleteAnchor2(BaseTestModel):
    value = models.IntegerField()


class DeleteAnchor3(BaseTestModel):
    value = models.IntegerField()


class DeleteAnchor4(BaseTestModel):
    value = models.IntegerField()


class DeleteBaseModel(BaseTestModel):
    my_id = models.AutoField(primary_key=True)
    char_field = models.CharField(max_length=20)
    int_field = models.IntegerField()
    int_field2 = models.IntegerField(db_column='non-default_db_column')
    int_field3 = models.IntegerField(unique=True)
    fk_field1 = models.ForeignKey(DeleteAnchor1,
                                  on_delete=models.CASCADE)
    m2m_field1 = models.ManyToManyField(DeleteAnchor3)
    m2m_field2 = models.ManyToManyField(DeleteAnchor4,
                                        db_table='non-default_m2m_table')


class CustomDeleteTableModel(BaseTestModel):
    value = models.IntegerField()
    alt_value = models.CharField(max_length=20)

    class Meta(BaseTestModel.Meta):
        db_table = 'custom_table_name'


class DeleteFieldTests(EvolutionTestCase):
    """Testing DeleteField mutations."""
    sql_mapping_key = 'delete_field'
    default_base_model = DeleteBaseModel
    default_extra_models = [
        ('DeleteAnchor1', DeleteAnchor1),
        ('DeleteAnchor2', DeleteAnchor2),
        ('DeleteAnchor3', DeleteAnchor3),
        ('DeleteAnchor4', DeleteAnchor4),
    ]

    def test_with_bad_app(self):
        """Testing DeleteField with application not in signature"""
        mutation = DeleteField('TestModel', 'char_field1')

        message = (
            'Cannot delete the field "char_field1" on model '
            '"badapp.TestModel". The application could not be found in the '
            'signature.'
        )

        with self.assertRaisesMessage(SimulationFailure, message):
            mutation.run_simulation(app_label='badapp',
                                    project_sig=ProjectSignature(),
                                    database_state=None)

    def test_with_bad_model(self):
        """Testing DeleteField with model not in signature"""
        mutation = DeleteField('TestModel', 'char_field1')

        project_sig = ProjectSignature()
        project_sig.add_app_sig(AppSignature(app_id='tests'))

        message = (
            'Cannot delete the field "char_field1" on model '
            '"tests.TestModel". The model could not be found in the '
            'signature.'
        )

        with self.assertRaisesMessage(SimulationFailure, message):
            mutation.run_simulation(app_label='tests',
                                    project_sig=project_sig,
                                    database_state=None)

    def test_with_bad_field(self):
        """Testing DeleteField with field not in signature"""
        mutation = DeleteField('TestModel', 'char_field1')

        model_sig = ModelSignature(model_name='TestModel',
                                   table_name='tests_testmodel')

        app_sig = AppSignature(app_id='tests')
        app_sig.add_model_sig(model_sig)

        project_sig = ProjectSignature()
        project_sig.add_app_sig(app_sig)

        message = (
            'Cannot delete the field "char_field1" on model '
            '"tests.TestModel". The field could not be found in the '
            'signature.'
        )

        with self.assertRaisesMessage(SimulationFailure, message):
            mutation.run_simulation(app_label='tests',
                                    project_sig=project_sig,
                                    database_state=None)

    def test_delete(self):
        """Testing DeleteField with a typical column"""
        class DestModel(BaseTestModel):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)
            int_field2 = models.IntegerField(db_column='non-default_db_column')
            int_field3 = models.IntegerField(unique=True)
            fk_field1 = models.ForeignKey(DeleteAnchor1,
                                          on_delete=models.CASCADE)
            m2m_field1 = models.ManyToManyField(DeleteAnchor3)
            m2m_field2 = models.ManyToManyField(
                DeleteAnchor4,
                db_table='non-default_m2m_table')

        self.perform_evolution_tests(
            DestModel,
            [
                DeleteField('TestModel', 'int_field'),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'int_field' has been deleted"),
            [
                "DeleteField('TestModel', 'int_field')",
            ],
            'DefaultNamedColumnModel')

    def test_delete_with_custom_column_name(self):
        """Testing DeleteField with custom column name"""
        class DestModel(BaseTestModel):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)
            int_field = models.IntegerField()
            int_field3 = models.IntegerField(unique=True)
            fk_field1 = models.ForeignKey(DeleteAnchor1,
                                          on_delete=models.CASCADE)
            m2m_field1 = models.ManyToManyField(DeleteAnchor3)
            m2m_field2 = models.ManyToManyField(
                DeleteAnchor4,
                db_table='non-default_m2m_table')

        self.perform_evolution_tests(
            DestModel,
            [
                DeleteField('TestModel', 'int_field2'),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'int_field2' has been deleted"),
            [
                "DeleteField('TestModel', 'int_field2')",
            ],
            'NonDefaultNamedColumnModel')

    def test_delete_with_unique(self):
        """Testing DeleteField with unique=True"""
        class DestModel(BaseTestModel):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)
            int_field = models.IntegerField()
            int_field2 = models.IntegerField(db_column='non-default_db_column')
            fk_field1 = models.ForeignKey(DeleteAnchor1,
                                          on_delete=models.CASCADE)
            m2m_field1 = models.ManyToManyField(DeleteAnchor3)
            m2m_field2 = models.ManyToManyField(
                DeleteAnchor4,
                db_table='non-default_m2m_table')

        self.perform_evolution_tests(
            DestModel,
            [
                DeleteField('TestModel', 'int_field3'),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'int_field3' has been deleted"),
            [
                "DeleteField('TestModel', 'int_field3')",
            ],
            'ConstrainedColumnModel')

    def test_delete_many_to_many_field(self):
        """Testing DeleteField with ManyToManyField"""
        class DestModel(BaseTestModel):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)
            int_field = models.IntegerField()
            int_field2 = models.IntegerField(db_column='non-default_db_column')
            int_field3 = models.IntegerField(unique=True)
            fk_field1 = models.ForeignKey(DeleteAnchor1,
                                          on_delete=models.CASCADE)
            m2m_field2 = models.ManyToManyField(
                DeleteAnchor4,
                db_table='non-default_m2m_table')

        self.perform_evolution_tests(
            DestModel,
            [
                DeleteField('TestModel', 'm2m_field1'),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'm2m_field1' has been deleted"),
            [
                "DeleteField('TestModel', 'm2m_field1')",
            ],
            'DefaultManyToManyModel')

    def test_delete_many_to_many_field_custom_table(self):
        """Testing DeleteField with ManyToManyField and custom table"""
        class DestModel(BaseTestModel):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)
            int_field = models.IntegerField()
            int_field2 = models.IntegerField(db_column='non-default_db_column')
            int_field3 = models.IntegerField(unique=True)
            fk_field1 = models.ForeignKey(DeleteAnchor1,
                                          on_delete=models.CASCADE)
            m2m_field1 = models.ManyToManyField(DeleteAnchor3)

        self.perform_evolution_tests(
            DestModel,
            [
                DeleteField('TestModel', 'm2m_field2'),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'm2m_field2' has been deleted"),
            [
                "DeleteField('TestModel', 'm2m_field2')",
            ],
            'NonDefaultManyToManyModel')

    def test_delete_foreign_key(self):
        """Testing DeleteField with ForeignKey"""
        class DestModel(BaseTestModel):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)
            int_field = models.IntegerField()
            int_field2 = models.IntegerField(db_column='non-default_db_column')
            int_field3 = models.IntegerField(unique=True)
            m2m_field1 = models.ManyToManyField(DeleteAnchor3)
            m2m_field2 = models.ManyToManyField(
                DeleteAnchor4,
                db_table='non-default_m2m_table')

        self.perform_evolution_tests(
            DestModel,
            [
                DeleteField('TestModel', 'fk_field1'),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'fk_field1' has been deleted"),
            [
                "DeleteField('TestModel', 'fk_field1')",
            ],
            'DeleteForeignKeyModel')

    def test_delete_column_from_custom_table(self):
        """Testing DeleteField with custom table name"""
        class DestModel(BaseTestModel):
            alt_value = models.CharField(max_length=20)

            class Meta(BaseTestModel.Meta):
                db_table = 'custom_table_name'

        self.set_base_model(CustomDeleteTableModel, name='CustomTableModel')

        self.perform_evolution_tests(
            DestModel,
            [
                DeleteField('CustomTableModel', 'value'),
            ],
            ("In model tests.CustomTableModel:\n"
             "    Field 'value' has been deleted"),
            [
                "DeleteField('CustomTableModel', 'value')",
            ],
            'DeleteColumnCustomTableModel',
            model_name='CustomTableModel')

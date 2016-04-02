from django.db import models

from django_evolution.mutations import (AddField, ChangeField, DeleteField,
                                        DeleteModel, RenameField, RenameModel,
                                        SQLMutation)
from django_evolution.tests.base_test_case import EvolutionTestCase


class BaseModel(models.Model):
    my_id = models.AutoField(primary_key=True)
    char_field = models.CharField(max_length=20)


class ReffedPreprocModel(models.Model):
    value = models.IntegerField()


class PreprocessingTests(EvolutionTestCase):
    """Testing pre-processing of mutations."""
    sql_mapping_key = 'preprocessing'
    default_base_model = BaseModel

    def test_add_delete_field(self):
        """Testing pre-processing AddField + DeleteField"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)

        self.perform_evolution_tests(
            DestModel,
            [
                AddField('TestModel', 'added_field', models.CharField,
                         initial='', max_length=20),
                DeleteField('TestModel', 'added_field'),
            ],
            '',
            [],
            'noop',
            expect_noop=True)

    def test_add_delete_add_field(self):
        """Testing pre-processing AddField + DeleteField + AddField"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)
            added_field = models.IntegerField()

        self.perform_evolution_tests(
            DestModel,
            [
                AddField('TestModel', 'added_field', models.CharField,
                         initial='', max_length=20),
                DeleteField('TestModel', 'added_field'),
                AddField('TestModel', 'added_field', models.IntegerField,
                         initial=42)
            ],
            ("In model tests.TestModel:\n"
             "    Field 'added_field' has been added"),
            [
                "AddField('TestModel', 'added_field', models.IntegerField,"
                " initial=<<USER VALUE REQUIRED>>)",
            ],
            'add_delete_add_field')

    def test_add_delete_add_rename_field(self):
        """Testing pre-processing AddField + DeleteField + AddField +
        RenameField
        """
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)
            renamed_field = models.IntegerField()

        self.perform_evolution_tests(
            DestModel,
            [
                AddField('TestModel', 'added_field', models.CharField,
                         initial='', max_length=20),
                DeleteField('TestModel', 'added_field'),
                AddField('TestModel', 'added_field', models.IntegerField,
                         initial=42),
                RenameField('TestModel', 'added_field', 'renamed_field'),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'renamed_field' has been added"),
            [
                "AddField('TestModel', 'renamed_field', models.IntegerField,"
                " initial=<<USER VALUE REQUIRED>>)",
            ],
            'add_delete_add_rename_field')

    def test_add_change_field(self):
        """Testing pre-processing AddField + ChangeField"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)
            added_field = models.CharField(max_length=50, null=True)

        self.perform_evolution_tests(
            DestModel,
            [
                AddField('TestModel', 'added_field', models.CharField,
                         initial='foo', max_length=20),
                ChangeField('TestModel', 'added_field', null=True,
                            initial='bar', max_length=50),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'added_field' has been added"),
            [
                "AddField('TestModel', 'added_field', models.CharField,"
                " max_length=50, null=True)",
            ],
            'add_change_field')

    def test_add_change_change_field(self):
        """Testing pre-processing AddField + ChangeField + ChangeField"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)
            added_field = models.CharField(max_length=50, null=True)

        self.perform_evolution_tests(
            DestModel,
            [
                AddField('TestModel', 'added_field', models.CharField,
                         initial='foo', max_length=20),
                ChangeField('TestModel', 'added_field', null=True,
                            initial='bar', max_length=30),
                ChangeField('TestModel', 'added_field',
                            initial='bar', max_length=50),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'added_field' has been added"),
            [
                "AddField('TestModel', 'added_field', models.CharField,"
                " max_length=50, null=True)",
            ],
            'add_change_field')

    def test_add_change_delete_field(self):
        """Testing pre-processing AddField + ChangeField + DeleteField"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)

        self.perform_evolution_tests(
            DestModel,
            [
                AddField('TestModel', 'added_field', models.CharField,
                         initial='foo', max_length=20),
                ChangeField('TestModel', 'added_field', null=True),
                DeleteField('TestModel', 'added_field'),
            ],
            '',
            [],
            'noop',
            expect_noop=True)

    def test_add_change_rename_field(self):
        """Testing pre-processing AddField + ChangeField + RenameField"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)
            renamed_field = models.CharField(max_length=50, null=True)

        self.perform_evolution_tests(
            DestModel,
            [
                AddField('TestModel', 'added_field', models.CharField,
                         initial='foo', max_length=20),
                ChangeField('TestModel', 'added_field', null=True,
                            initial='bar', max_length=50),
                RenameField('TestModel', 'added_field', 'renamed_field'),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'renamed_field' has been added"),
            [
                "AddField('TestModel', 'renamed_field', models.CharField,"
                " max_length=50, null=True)",
            ],
            'add_change_rename_field')

    def test_add_rename_change_field(self):
        """Testing pre-processing AddField + RenameField + ChangeField"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)
            renamed_field = models.CharField(max_length=50, null=True)

        self.perform_evolution_tests(
            DestModel,
            [
                AddField('TestModel', 'added_field', models.CharField,
                         initial='foo', max_length=20),
                RenameField('TestModel', 'added_field', 'renamed_field'),
                ChangeField('TestModel', 'renamed_field', null=True,
                            initial='bar', max_length=50),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'renamed_field' has been added"),
            [
                "AddField('TestModel', 'renamed_field', models.CharField,"
                " max_length=50, null=True)",
            ],
            'add_rename_change_field')

    def test_add_rename_change_rename_change_field(self):
        """Testing pre-processing AddField + RenameField + ChangeField +
        RenameField + ChangeField
        """
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)
            renamed_field = models.CharField(max_length=50, null=True)

        self.perform_evolution_tests(
            DestModel,
            [
                AddField('TestModel', 'added_field', models.CharField,
                         initial='foo', max_length=20),
                RenameField('TestModel', 'added_field', 'foo_field'),
                ChangeField('TestModel', 'foo_field', null=True),
                RenameField('TestModel', 'foo_field', 'renamed_field'),
                ChangeField('TestModel', 'renamed_field', max_length=50),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'renamed_field' has been added"),
            [
                "AddField('TestModel', 'renamed_field', models.CharField,"
                " max_length=50, null=True)",
            ],
            'add_rename_change_rename_change_field')

    def test_add_rename_delete(self):
        """Testing pre-processing AddField + RenameField + DeleteField"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)

        self.perform_evolution_tests(
            DestModel,
            [
                AddField('TestModel', 'added_field', models.CharField,
                         initial='foo', max_length=20),
                RenameField('TestModel', 'added_field', 'renamed_field'),
                DeleteField('TestModel', 'renamed_field'),
            ],
            '',
            [],
            'noop',
            expect_noop=True)

    def test_add_rename_field_with_db_column(self):
        """Testing pre-processing AddField + RenameField with
        RenameField.db_column
        """
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)
            renamed_field = models.CharField(max_length=50, null=True,
                                             db_column='added_field')

        self.perform_evolution_tests(
            DestModel,
            [
                AddField('TestModel', 'added_field', models.CharField,
                         max_length=50, null=True),
                RenameField('TestModel', 'added_field', 'renamed_field',
                            db_column='added_field'),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'renamed_field' has been added"),
            [
                "AddField('TestModel', 'renamed_field', models.CharField,"
                " max_length=50, null=True, db_column='added_field')",
            ],
            'add_rename_field_with_db_column')

    def test_add_field_rename_model(self):
        """Testing pre-processing AddField + RenameModel"""
        class RenamedReffedPreprocModel(models.Model):
            value = models.IntegerField()

            class Meta:
                db_table = 'tests_reffedpreprocmodel'

        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)
            added_field = models.ForeignKey(RenamedReffedPreprocModel,
                                            null=True)

        self.set_base_model(
            self.default_base_model,
            extra_models=[
                ('ReffedPreprocModel', ReffedPreprocModel)
            ])

        # Prepare the renamed model in the end signature.
        end, end_sig = self.make_end_signatures(DestModel, 'TestModel')
        end_tests_sig = end_sig['tests']
        end_tests_sig['RenamedReffedPreprocModel'] = \
            end_tests_sig.pop('ReffedPreprocModel')

        fields_sig = end_tests_sig['TestModel']['fields']
        fields_sig['added_field']['related_model'] = \
            'tests.RenamedReffedPreprocModel'

        self.perform_evolution_tests(
            DestModel,
            [
                AddField('TestModel', 'added_field', models.ForeignKey,
                         null=True, related_model='tests.ReffedPreprocModel'),
                RenameModel('ReffedPreprocModel', 'RenamedReffedPreprocModel',
                            db_table='tests_reffedpreprocmodel'),
            ],
            ("The model tests.ReffedPreprocModel has been deleted\n"
             "In model tests.TestModel:\n"
             "    Field 'added_field' has been added"),
            [
                "AddField('TestModel', 'added_field', models.ForeignKey,"
                " null=True, related_model='tests.RenamedReffedPreprocModel')",
                "DeleteModel('ReffedPreprocModel')",
            ],
            'add_field_rename_model',
            end=end,
            end_sig=end_sig)

    def test_add_rename_field_rename_model(self):
        """Testing pre-processing AddField + RenameField + RenameModel"""
        class RenamedReffedPreprocModel(models.Model):
            value = models.IntegerField()

            class Meta:
                db_table = 'tests_reffedpreprocmodel'

        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)
            renamed_field = models.ForeignKey(RenamedReffedPreprocModel,
                                              null=True)

        self.set_base_model(
            self.default_base_model,
            extra_models=[
                ('ReffedPreprocModel', ReffedPreprocModel)
            ])

        # Prepare the renamed model in the end signature.
        end, end_sig = self.make_end_signatures(DestModel, 'TestModel')
        end_tests_sig = end_sig['tests']
        end_tests_sig['RenamedReffedPreprocModel'] = \
            end_tests_sig.pop('ReffedPreprocModel')

        fields_sig = end_tests_sig['TestModel']['fields']
        fields_sig['renamed_field']['related_model'] = \
            'tests.RenamedReffedPreprocModel'

        self.perform_evolution_tests(
            DestModel,
            [
                AddField('TestModel', 'added_field', models.ForeignKey,
                         null=True,
                         related_model='tests.ReffedPreprocModel'),
                RenameField('TestModel', 'added_field', 'renamed_field'),
                RenameModel('ReffedPreprocModel', 'RenamedReffedPreprocModel',
                            db_table='tests_reffedpreprocmodel'),
            ],
            ("The model tests.ReffedPreprocModel has been deleted\n"
             "In model tests.TestModel:\n"
             "    Field 'renamed_field' has been added"),
            [
                "AddField('TestModel', 'renamed_field', models.ForeignKey,"
                " null=True, related_model='tests.RenamedReffedPreprocModel')",
                "DeleteModel('ReffedPreprocModel')",
            ],
            'add_rename_field_rename_model',
            end=end,
            end_sig=end_sig)

    def test_add_sql_delete(self):
        """Testing pre-processing AddField + SQLMutation + DeleteField"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)

        self.perform_evolution_tests(
            DestModel,
            [
                AddField('TestModel', 'added_field', models.CharField,
                         initial='foo', max_length=20),
                SQLMutation('dummy-sql',
                            ['-- Comment --'],
                            lambda app_label, proj_sig: None),
                DeleteField('TestModel', 'added_field'),
            ],
            '',
            [
                "DeleteField('TestModel', 'char_field')",
            ],
            'add_sql_delete',
            expect_noop=True)

    def test_change_delete_field(self):
        """Testing pre-processing ChangeField + DeleteField"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'char_field', null=True),
                DeleteField('TestModel', 'char_field'),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'char_field' has been deleted"),
            [
                "DeleteField('TestModel', 'char_field')",
            ],
            'delete_char_field')

    def test_change_rename_field(self):
        """Testing pre-processing ChangeField + RenameField"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            renamed_field = models.CharField(max_length=20, null=True)

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'char_field', null=True),
                RenameField('TestModel', 'char_field', 'renamed_field'),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'renamed_field' has been added\n"
             "    Field 'char_field' has been deleted"),
            [
                "AddField('TestModel', 'renamed_field', models.CharField,"
                " max_length=20, null=True)",

                "DeleteField('TestModel', 'char_field')",
            ],
            'change_rename_field')

    def test_change_rename_change_rename_field(self):
        """Testing pre-processing ChangeField + RenameField + ChangeField +
        RenameField
        """
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            renamed_field = models.CharField(max_length=30, null=True)

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'char_field', max_length=30),
                RenameField('TestModel', 'char_field', 'foo_field'),
                ChangeField('TestModel', 'foo_field', null=True),
                RenameField('TestModel', 'foo_field', 'renamed_field'),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'renamed_field' has been added\n"
             "    Field 'char_field' has been deleted"),
            [
                "AddField('TestModel', 'renamed_field', models.CharField,"
                " max_length=30, null=True)",

                "DeleteField('TestModel', 'char_field')",
            ],
            'change_rename_change_rename_field')

    def test_change_rename_delete_field(self):
        """Testing pre-processing ChangeField + RenameField + DeleteField"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'char_field', null=True),
                RenameField('TestModel', 'char_field', 'renamed_field'),
                DeleteField('TestModel', 'renamed_field'),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'char_field' has been deleted"),
            [
                "DeleteField('TestModel', 'char_field')",
            ],
            'delete_char_field')

    def test_rename_add_field(self):
        """Testing pre-processing RenameField + AddField"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            renamed_field = models.CharField(max_length=20)
            char_field = models.CharField(max_length=50, null=True)

        self.perform_evolution_tests(
            DestModel,
            [
                RenameField('TestModel', 'char_field', 'renamed_field'),
                AddField('TestModel', 'char_field', models.CharField,
                         max_length=50, null=True),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'renamed_field' has been added\n"
             "    In field 'char_field':\n"
             "        Property 'max_length' has changed\n"
             "        Property 'null' has changed"),
            [
                "AddField('TestModel', 'renamed_field', models.CharField,"
                " initial=<<USER VALUE REQUIRED>>, max_length=20)",

                "ChangeField('TestModel', 'char_field', initial=None,"
                " max_length=50, null=True)",
            ],
            'rename_add_field')

    def test_rename_delete_field(self):
        """Testing pre-processing RenameField + DeleteField"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)

        self.perform_evolution_tests(
            DestModel,
            [
                RenameField('TestModel', 'char_field', 'renamed_field'),
                DeleteField('TestModel', 'renamed_field'),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'char_field' has been deleted"),
            [
                "DeleteField('TestModel', 'char_field')",
            ],
            'delete_char_field')

    def test_rename_change_delete_field(self):
        """Testing pre-processing RenameField + ChangeField + DeleteField"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)

        self.perform_evolution_tests(
            DestModel,
            [
                RenameField('TestModel', 'char_field', 'renamed_field'),
                ChangeField('TestModel', 'renamed_field', null=True),
                DeleteField('TestModel', 'renamed_field'),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'char_field' has been deleted"),
            [
                "DeleteField('TestModel', 'char_field')",
            ],
            'delete_char_field')

    def test_rename_change_rename_change_field(self):
        """Testing pre-processing RenameField + ChangeField + RenameField +
        ChangeField
        """
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            renamed_field = models.CharField(max_length=50, null=True)

        self.perform_evolution_tests(
            DestModel,
            [
                RenameField('TestModel', 'char_field', 'foo_field'),
                ChangeField('TestModel', 'foo_field', max_length=30,
                            null=True),
                RenameField('TestModel', 'foo_field', 'renamed_field'),
                ChangeField('TestModel', 'renamed_field', max_length=50),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'renamed_field' has been added\n"
             "    Field 'char_field' has been deleted"),
            [
                "AddField('TestModel', 'renamed_field', models.CharField,"
                " max_length=50, null=True)",

                "DeleteField('TestModel', 'char_field')",
            ],
            'rename_change_rename_change_field')

    def test_rename_rename_field(self):
        """Testing pre-processing RenameField + RenameField"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            renamed_field = models.CharField(max_length=20)

        self.perform_evolution_tests(
            DestModel,
            [
                RenameField('TestModel', 'char_field', 'foo_field'),
                RenameField('TestModel', 'foo_field', 'renamed_field'),
            ],
            ("In model tests.TestModel:\n"
             "    Field 'renamed_field' has been added\n"
             "    Field 'char_field' has been deleted"),
            [
                "AddField('TestModel', 'renamed_field', models.CharField,"
                " initial=<<USER VALUE REQUIRED>>, max_length=20)",

                "DeleteField('TestModel', 'char_field')",
            ],
            'rename_rename_field')

    def test_rename_rename_model(self):
        """Testing pre-processing RenameModel + RenameModel"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)

            class Meta:
                db_table = 'tests_testmodel'

        self.perform_evolution_tests(
            DestModel,
            [
                RenameModel('TestModel', 'TempModel',
                            db_table='tests_testmodel'),
                RenameModel('TempModel', 'DestModel',
                            db_table='tests_testmodel'),
            ],
            "The model tests.TestModel has been deleted",
            [
                "DeleteModel('TestModel')",
            ],
            'noop',
            model_name='DestModel')

    def test_rename_delete_model(self):
        """Testing pre-processing RenameModel + DeleteModel"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            char_field = models.CharField(max_length=20)

            class Meta:
                db_table = 'tests_testmodel'

        self.perform_evolution_tests(
            DestModel,
            [
                RenameModel('TestModel', 'TempModel',
                            db_table='tests_testmodel'),
                DeleteModel('TempModel'),
            ],
            "The model tests.TestModel has been deleted",
            [
                "DeleteModel('TestModel')",
            ],
            'rename_delete_model',
            model_name='DestModel')

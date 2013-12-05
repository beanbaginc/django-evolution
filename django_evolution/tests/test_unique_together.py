from django.db import models

from django_evolution.mutations import ChangeMeta
from django_evolution.tests.base_test_case import (ChangeAnchor1,
                                                   EvolutionTestCase)


class NoUniqueTogetherBaseModel(models.Model):
    int_field1 = models.IntegerField()
    int_field2 = models.IntegerField()
    char_field1 = models.CharField(max_length=20)
    char_field2 = models.CharField(max_length=40)


class UniqueTogetherBaseModel(models.Model):
    int_field1 = models.IntegerField()
    int_field2 = models.IntegerField()
    char_field1 = models.CharField(max_length=20)
    char_field2 = models.CharField(max_length=40)

    class Meta:
        unique_together = [('int_field1', 'char_field1')]


class UniqueTogetherTests(EvolutionTestCase):
    """Testing ChangeMeta with adding unique_together"""
    sql_mapping_key = 'unique_together'

    DIFF_TEXT = (
        "In model tests.TestModel:\n"
        "    Meta property 'unique_together' has changed"
    )

    def get_default_base_model(self):
        return None

    def test_keeping_empty(self):
        """Testing ChangeMeta(unique_together) and keeping list empty"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                unique_together = []

        self.set_base_model(NoUniqueTogetherBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel', 'unique_together', []),
            ],
            None,
            None,
            None,
            expect_noop=True)

    def test_setting_from_empty(self):
        """Testing ChangeMeta(unique_together) and setting to valid list"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                unique_together = [('int_field1', 'char_field1')]

        self.set_base_model(NoUniqueTogetherBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel', 'unique_together',
                           [('int_field1', 'char_field1')]),
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'unique_together',"
                " [('int_field1', 'char_field1')])"
            ],
            'setting_from_empty')

    def test_replace_list(self):
        """Testing ChangeMeta(unique_together) and replacing list"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                unique_together = [('int_field2', 'char_field2')]

        self.set_base_model(UniqueTogetherBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel', 'unique_together',
                           [('int_field2', 'char_field2')]),
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'unique_together',"
                " [('int_field2', 'char_field2')])"
            ],
            'replace_list')

    def test_append_list(self):
        """Testing ChangeMeta(unique_together) and appending list"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                unique_together = [('int_field1', 'char_field1'),
                                   ('int_field2', 'char_field2')]

        self.set_base_model(UniqueTogetherBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel', 'unique_together',
                           [('int_field1', 'char_field1'),
                            ('int_field2', 'char_field2')]),
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'unique_together',"
                " [('int_field1', 'char_field1'),"
                " ('int_field2', 'char_field2')])"
            ],
            'append_list')

    def test_removing(self):
        """Testing ChangeMeta(unique_together) and removing property"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

        self.set_base_model(UniqueTogetherBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel', 'unique_together', [])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'unique_together', [])"
            ],
            'removing')

    def test_missing_indexes(self):
        """Testing ChangeMeta(unique_together) and old missing indexes"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                unique_together = [('char_field1', 'char_field2')]

        self.set_base_model(UniqueTogetherBaseModel)

        # Remove the indexes from the database signature, to simulate
        # the indexes not being found in the database. The evolution
        # should still work.
        self.database_sig['tests_testmodel']['indexes'] = {}

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel', 'unique_together',
                           [('char_field1', 'char_field2')])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'unique_together',"
                " [('char_field1', 'char_field2')])"
            ],
            'ignore_missing_indexes',
            rescan_indexes=False)

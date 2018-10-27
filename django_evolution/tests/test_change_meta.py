"""Unit tests for the ChangeMeta mutation."""

from __future__ import unicode_literals

from django.db import models
from nose import SkipTest

try:
    # Django >= 1.11
    from django.db.models import Index
except ImportError:
    # Django <= 1.10
    Index = None

from django_evolution.mutations import ChangeMeta
from django_evolution.support import supports_indexes, supports_index_together
from django_evolution.tests.base_test_case import EvolutionTestCase


class ChangeMetaPlainBaseModel(models.Model):
    int_field1 = models.IntegerField()
    int_field2 = models.IntegerField()
    char_field1 = models.CharField(max_length=20)
    char_field2 = models.CharField(max_length=40)


class ChangeMetaIndexesBaseModel(models.Model):
    int_field1 = models.IntegerField()
    int_field2 = models.IntegerField()
    char_field1 = models.CharField(max_length=20)
    char_field2 = models.CharField(max_length=40)

    class Meta:
        if Index:
            indexes = [
                Index(fields=['int_field1']),
                Index(fields=['char_field1', '-char_field2'],
                      name='my_custom_index'),
            ]


class ChangeMetaIndexTogetherBaseModel(models.Model):
    int_field1 = models.IntegerField()
    int_field2 = models.IntegerField()
    char_field1 = models.CharField(max_length=20)
    char_field2 = models.CharField(max_length=40)

    class Meta:
        index_together = [('int_field1', 'char_field1')]


class ChangeMetaUniqueTogetherBaseModel(models.Model):
    int_field1 = models.IntegerField()
    int_field2 = models.IntegerField()
    char_field1 = models.CharField(max_length=20)
    char_field2 = models.CharField(max_length=40)

    class Meta:
        unique_together = [('int_field1', 'char_field1')]


class ChangeMetaIndexesTests(EvolutionTestCase):
    """Unit tests for ChangeMeta with indexes."""

    sql_mapping_key = 'indexes'

    DIFF_TEXT = (
        "In model tests.TestModel:\n"
        "    Meta property 'indexes' has changed"
    )

    @classmethod
    def setUpClass(cls):
        super(ChangeMetaIndexesTests, cls).setUpClass()

        if not supports_indexes:
            raise SkipTest('Meta.indexes is not supported on this version '
                           'of Django')

    def test_keeping_empty(self):
        """Testing ChangeMeta(indexes) and keeping list empty"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                indexes = []

        self.set_base_model(ChangeMetaPlainBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel', 'indexes', []),
            ],
            None,
            None,
            None,
            expect_noop=True)

    def test_setting_from_empty(self):
        """Testing ChangeMeta(indexes) and setting to valid list"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                indexes = [
                    Index(fields=['int_field1']),
                    Index(fields=['char_field1', '-char_field2'],
                          name='my_custom_index'),
                ]

        self.set_base_model(ChangeMetaPlainBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta(
                    'TestModel',
                    'indexes',
                    [
                        {
                            'fields': ['int_field1'],
                        },
                        {
                            'fields': ['char_field1', '-char_field2'],
                            'name': 'my_custom_index',
                        },
                    ])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'indexes',"
                " [{'fields': ['int_field1']},"
                " {'fields': ['char_field1', '-char_field2'],"
                " 'name': 'my_custom_index'}])"
            ],
            'setting_from_empty')

    def test_replace_list(self):
        """Testing ChangeMeta(indexes) and replacing list"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                indexes = [
                    Index(fields=['int_field2']),
                ]

        self.set_base_model(ChangeMetaIndexesBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel', 'indexes',
                           [{'fields': ['int_field2']}])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'indexes',"
                " [{'fields': ['int_field2']}])"
            ],
            'replace_list')

    def test_append_list(self):
        """Testing ChangeMeta(indexes) and appending list"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                indexes = [
                    Index(fields=['int_field1']),
                    Index(fields=['char_field1', '-char_field2'],
                          name='my_custom_index'),
                    Index(fields=['int_field2']),
                ]

        self.set_base_model(ChangeMetaIndexesBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta(
                    'TestModel',
                    'indexes',
                    [
                        {
                            'fields': ['int_field1'],
                        },
                        {
                            'fields': ['char_field1', '-char_field2'],
                            'name': 'my_custom_index',
                        },
                        {
                            'fields': ['int_field2'],
                        },
                    ])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'indexes',"
                " [{'fields': ['int_field1']},"
                " {'fields': ['char_field1', '-char_field2'],"
                " 'name': 'my_custom_index'},"
                " {'fields': ['int_field2']}])"
            ],
            'append_list')

    def test_removing(self):
        """Testing ChangeMeta(indexes) and removing property"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

        self.set_base_model(ChangeMetaIndexesBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel', 'indexes', [])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'indexes', [])"
            ],
            'removing')

    def test_missing_indexes(self):
        """Testing ChangeMeta(indexes) and old missing indexes"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                indexes = [
                    Index(fields=['int_field2']),
                ]

        self.set_base_model(ChangeMetaIndexesBaseModel)

        # Remove the indexes from the database state, to simulate the indexes
        # not being found in the database. The evolution should still work.
        self.database_state.clear_indexes('tests_testmodel')

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel', 'indexes',
                           [{'fields': ['int_field2']}])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'indexes',"
                " [{'fields': ['int_field2']}])"
            ],
            'ignore_missing_indexes',
            rescan_indexes=False)


class ChangeMetaIndexTogetherTests(EvolutionTestCase):
    """Unit tests for ChangeMeta with index_together."""

    sql_mapping_key = 'index_together'

    DIFF_TEXT = (
        "In model tests.TestModel:\n"
        "    Meta property 'index_together' has changed"
    )

    @classmethod
    def setUpClass(cls):
        super(ChangeMetaIndexTogetherTests, cls).setUpClass()

        if not supports_index_together:
            raise SkipTest('Meta.index_together is not supported on this '
                           'version of Django')

    def test_keeping_empty(self):
        """Testing ChangeMeta(index_together) and keeping list empty"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                index_together = []

        self.set_base_model(ChangeMetaPlainBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel', 'index_together', []),
            ],
            None,
            None,
            None,
            expect_noop=True)

    def test_setting_from_empty(self):
        """Testing ChangeMeta(index_together) and setting to valid list"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                index_together = [('int_field1', 'char_field1')]

        self.set_base_model(ChangeMetaPlainBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel', 'index_together',
                           [('int_field1', 'char_field1')]),
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'index_together',"
                " [('int_field1', 'char_field1')])"
            ],
            'setting_from_empty')

    def test_replace_list(self):
        """Testing ChangeMeta(index_together) and replacing list"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                index_together = [('int_field2', 'char_field2')]

        self.set_base_model(ChangeMetaIndexTogetherBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel', 'index_together',
                           [('int_field2', 'char_field2')]),
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'index_together',"
                " [('int_field2', 'char_field2')])"
            ],
            'replace_list')

    def test_append_list(self):
        """Testing ChangeMeta(index_together) and appending list"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                index_together = [('int_field1', 'char_field1'),
                                  ('int_field2', 'char_field2')]

        self.set_base_model(ChangeMetaIndexTogetherBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel', 'index_together',
                           [('int_field1', 'char_field1'),
                            ('int_field2', 'char_field2')]),
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'index_together',"
                " [('int_field1', 'char_field1'),"
                " ('int_field2', 'char_field2')])"
            ],
            'append_list')

    def test_removing(self):
        """Testing ChangeMeta(index_together) and removing property"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

        self.set_base_model(ChangeMetaIndexTogetherBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel', 'index_together', [])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'index_together', [])"
            ],
            'removing')

    def test_missing_indexes(self):
        """Testing ChangeMeta(index_together) and old missing indexes"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                index_together = [('char_field1', 'char_field2')]

        self.set_base_model(ChangeMetaIndexTogetherBaseModel)

        # Remove the indexes from the database state, to simulate the indexes
        # not being found in the database. The evolution should still work.
        self.database_state.clear_indexes('tests_testmodel')

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel', 'index_together',
                           [('char_field1', 'char_field2')])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'index_together',"
                " [('char_field1', 'char_field2')])"
            ],
            'ignore_missing_indexes',
            rescan_indexes=False)


class ChangeMetaUniqueTogetherTests(EvolutionTestCase):
    """Unit tests for ChangeMeta with unique_together."""

    sql_mapping_key = 'unique_together'

    DIFF_TEXT = (
        "In model tests.TestModel:\n"
        "    Meta property 'unique_together' has changed"
    )

    def test_keeping_empty(self):
        """Testing ChangeMeta(unique_together) and keeping list empty"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                unique_together = []

        self.set_base_model(ChangeMetaPlainBaseModel)
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

        self.set_base_model(ChangeMetaPlainBaseModel)
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

        self.set_base_model(ChangeMetaUniqueTogetherBaseModel)
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

        self.set_base_model(ChangeMetaUniqueTogetherBaseModel)
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

        self.set_base_model(ChangeMetaUniqueTogetherBaseModel)
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

    def test_set_remove(self):
        """Testing ChangeMeta(unique_together) and setting indexes and removing
        one
        """
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                unique_together = [('int_field1', 'char_field1')]

        self.set_base_model(ChangeMetaPlainBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel', 'unique_together',
                           [('int_field1', 'char_field1'),
                            ('int_field2', 'char_field2')]),
                ChangeMeta('TestModel', 'unique_together',
                           [('int_field1', 'char_field1')])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'unique_together',"
                " [('int_field1', 'char_field1')])"
            ],
            'set_remove')

    def test_missing_indexes(self):
        """Testing ChangeMeta(unique_together) and old missing indexes"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                unique_together = [('char_field1', 'char_field2')]

        self.set_base_model(ChangeMetaUniqueTogetherBaseModel)

        # Remove the indexes from the database state, to simulate the indexes
        # not being found in the database. The evolution should still work.
        self.database_state.clear_indexes('tests_testmodel')

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

    def test_upgrade_from_v1_sig_no_indexes(self):
        """Testing ChangeMeta(unique_together) and upgrade from v1 signature
        with no changes and no indexes in database"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                unique_together = [('int_field1', 'char_field1')]

        self.set_base_model(ChangeMetaPlainBaseModel)

        # Pretend this is an older signature with the same unique_together.
        meta = self.start_sig['tests']['TestModel']['meta']
        del meta['__unique_together_applied']
        meta['unique_together'] = DestModel._meta.unique_together

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel', 'unique_together',
                           [('int_field1', 'char_field1')])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'unique_together',"
                " [('int_field1', 'char_field1')])"
            ],
            'upgrade_from_v1_sig',
            rescan_indexes=False)

    def test_upgrade_from_v1_sig_with_indexes(self):
        """Testing ChangeMeta(unique_together) and upgrade from v1 signature
        with no changes and with indexes in database"""
        class DestModel(models.Model):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta:
                unique_together = [('int_field1', 'char_field1')]

        self.set_base_model(ChangeMetaUniqueTogetherBaseModel)

        # Pretend this is an older signature with the same unique_together.
        meta = self.start_sig['tests']['TestModel']['meta']
        del meta['__unique_together_applied']

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel', 'unique_together',
                           [('int_field1', 'char_field1')])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'unique_together',"
                " [('int_field1', 'char_field1')])"
            ],
            None,
            rescan_indexes=False)

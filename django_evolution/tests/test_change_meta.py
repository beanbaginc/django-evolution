"""Unit tests for the ChangeMeta mutation."""

from __future__ import unicode_literals

from django.db import models
from django.db.models import F, Q

try:
    # Django >= 2.2
    from django.db.models import CheckConstraint, UniqueConstraint
except ImportError:
    # Django <= 2.1
    CheckConstraint = None
    UniqueConstraint = None

try:
    # Django >= 1.11
    from django.db.models import Index
except ImportError:
    # Django <= 1.10
    Index = None

from django_evolution.mutations import ChangeMeta
from django_evolution.support import (supports_constraints,
                                      supports_db_table_comments,
                                      supports_indexes)
from django_evolution.tests.base_test_case import EvolutionTestCase
from django_evolution.tests.decorators import (requires_change_meta_field,
                                               requires_index_feature,
                                               requires_meta_constraints,
                                               requires_meta_index_together,
                                               requires_meta_indexes)
from django_evolution.tests.models import BaseTestModel
from django_evolution.tests.utils import get_default_tablespace


class ChangeMetaPlainBaseModel(BaseTestModel):
    int_field1 = models.IntegerField()
    int_field2 = models.IntegerField()
    char_field1 = models.CharField(max_length=20)
    char_field2 = models.CharField(max_length=40)


class ChangeMetaConstraintsBaseModel(BaseTestModel):
    int_field1 = models.IntegerField()
    int_field2 = models.IntegerField()
    char_field1 = models.CharField(max_length=20)
    char_field2 = models.CharField(max_length=40)

    class Meta(BaseTestModel.Meta):
        if supports_constraints:
            # Django >= 2.2
            constraints = [
                # We have three types we want to test in our baseline here:
                #
                # 1. A Check constraint
                # 2. A Unique constraint *with* a condition
                # 3. A Unique constraint *without* a condition
                #
                # Not all databases will support all three, or even two of
                # these. Some will be ignored.
                CheckConstraint(name='base_check_constraint',
                                check=Q(char_field1__startswith='test')),
                UniqueConstraint(name='base_unique_constraint_condition',
                                 fields=['int_field1', 'char_field1'],
                                 condition=Q(int_field1__gte=10)),
                UniqueConstraint(name='base_unique_constraint_plain',
                                 fields=['int_field1', 'char_field1']),
            ]


class ChangeMetaDbTableCommentBaseModel(BaseTestModel):
    int_field1 = models.IntegerField()
    int_field2 = models.IntegerField()
    char_field1 = models.CharField(max_length=20)
    char_field2 = models.CharField(max_length=40)

    class Meta(BaseTestModel.Meta):
        if supports_db_table_comments:
            db_table_comment = 'Old comment.'


class ChangeMetaIndexesBaseModel(BaseTestModel):
    int_field1 = models.IntegerField()
    int_field2 = models.IntegerField()
    char_field1 = models.CharField(max_length=20)
    char_field2 = models.CharField(max_length=40)

    class Meta(BaseTestModel.Meta):
        if supports_indexes:
            # Django >= 1.11
            indexes = [
                Index(fields=['int_field1']),
                Index(fields=['char_field1', '-char_field2'],
                      name='my_custom_index'),
            ]


class ChangeMetaIndexTogetherBaseModel(BaseTestModel):
    int_field1 = models.IntegerField()
    int_field2 = models.IntegerField()
    char_field1 = models.CharField(max_length=20)
    char_field2 = models.CharField(max_length=40)

    class Meta(BaseTestModel.Meta):
        index_together = [('int_field1', 'char_field1')]


class ChangeMetaUniqueTogetherBaseModel(BaseTestModel):
    int_field1 = models.IntegerField()
    int_field2 = models.IntegerField()
    char_field1 = models.CharField(max_length=20)
    char_field2 = models.CharField(max_length=40)

    class Meta(BaseTestModel.Meta):
        unique_together = [('int_field1', 'char_field1')]


class BaseChangeMetaTestCase(EvolutionTestCase):
    """Base class for ChangeMeta test cases."""

    def default_create_test_data(self, db_name):
        """Create test data for the base model.

        Args:
            db_name (unicode):
                The name of the database to create models on.
        """
        self.base_model.objects.using(db_name).create(
            int_field1=100,
            int_field2=200,
            char_field1='test1',
            char_field2='test2')


class ChangeMetaConstraintsTests(BaseChangeMetaTestCase):
    """Unit tests for ChangeMeta with constraints."""

    sql_mapping_key = 'constraints'

    DIFF_TEXT = (
        "In model tests.TestModel:\n"
        "    Meta property 'constraints' has changed"
    )

    @classmethod
    @requires_meta_constraints
    def setUpClass(cls):
        super(ChangeMetaConstraintsTests, cls).setUpClass()

    def test_keeping_empty(self):
        """Testing ChangeMeta(constraints) and keeping list empty"""
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                constraints = []

        self.set_base_model(ChangeMetaPlainBaseModel)
        self.perform_evolution_tests(
            dest_model=DestModel,
            evolutions=[
                ChangeMeta('TestModel', 'constraints', []),
            ],
            expect_noop=True)

    def test_setting_valid_list(self):
        """Testing ChangeMeta(constraints) and setting to valid list"""
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                constraints = [
                    CheckConstraint(name='new_check_constraint',
                                    check=Q(char_field1__startswith='test')),
                    UniqueConstraint(name='new_unique_constraint_condition',
                                     fields=['int_field2'],
                                     condition=Q(int_field2=100)),
                    UniqueConstraint(name='new_unique_constraint_plain',
                                     fields=['int_field1', 'int_field2']),
                ]

        self.set_base_model(ChangeMetaPlainBaseModel)
        self.perform_evolution_tests(
            dest_model=DestModel,
            evolutions=[
                ChangeMeta(
                    'TestModel',
                    'constraints',
                    [
                        {
                            'type': CheckConstraint,
                            'name': 'new_check_constraint',
                            'check': Q(char_field1__startswith='test'),
                        },
                        {
                            'type': UniqueConstraint,
                            'name': 'new_unique_constraint_condition',
                            'condition': Q(int_field2=100),
                            'fields': ('int_field2',),
                        },
                        {
                            'type': UniqueConstraint,
                            'name': 'new_unique_constraint_plain',
                            'fields': ('int_field1', 'int_field2'),
                        },
                    ])
            ],
            diff_text=self.DIFF_TEXT,
            expected_hint=[
                "ChangeMeta('TestModel', 'constraints',"
                " [{'check': models.Q(char_field1__startswith='test'),"
                " 'name': 'new_check_constraint',"
                " 'type': models.CheckConstraint},"
                " {'condition': models.Q(int_field2=100),"
                " 'fields': ('int_field2',),"
                " 'name': 'new_unique_constraint_condition',"
                " 'type': models.UniqueConstraint},"
                " {'fields': ('int_field1', 'int_field2'),"
                " 'name': 'new_unique_constraint_plain',"
                " 'type': models.UniqueConstraint}])"
            ],
            sql_name='setting_from_empty')

    def test_replace_list(self):
        """Testing ChangeMeta(indexes) and replacing list"""
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                constraints = [
                    CheckConstraint(name='new_check_constraint',
                                    check=Q(char_field1__startswith='test')),
                    UniqueConstraint(name='new_unique_constraint_condition',
                                     condition=Q(char_field2='bar'),
                                     fields=['int_field2']),
                    UniqueConstraint(name='new_unique_constraint_plain',
                                     fields=['int_field1', 'char_field1']),
                ]

        self.set_base_model(ChangeMetaConstraintsBaseModel)
        self.perform_evolution_tests(
            dest_model=DestModel,
            evolutions=[
                ChangeMeta(
                    'TestModel',
                    'constraints',
                    [
                        {
                            'type': CheckConstraint,
                            'name': 'new_check_constraint',
                            'check': Q(char_field1__startswith='test'),
                        },
                        {
                            'type': UniqueConstraint,
                            'name': 'new_unique_constraint_condition',
                            'condition': Q(char_field2='bar'),
                            'fields': ('int_field2',),
                        },
                        {
                            'type': UniqueConstraint,
                            'name': 'new_unique_constraint_plain',
                            'fields': ('int_field1', 'char_field1'),
                        },
                    ])
            ],
            diff_text=self.DIFF_TEXT,
            expected_hint=[
                "ChangeMeta('TestModel', 'constraints',"
                " [{'check': models.Q(char_field1__startswith='test'),"
                " 'name': 'new_check_constraint',"
                " 'type': models.CheckConstraint},"
                " {'condition': models.Q(char_field2='bar'),"
                " 'fields': ('int_field2',),"
                " 'name': 'new_unique_constraint_condition',"
                " 'type': models.UniqueConstraint},"
                " {'fields': ('int_field1', 'char_field1'),"
                " 'name': 'new_unique_constraint_plain',"
                " 'type': models.UniqueConstraint}])"
            ],
            sql_name='replace_list')

    def test_append_list(self):
        """Testing ChangeMeta(constraints) and appending list"""
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                constraints = [
                    CheckConstraint(name='base_check_constraint',
                                    check=Q(char_field1__startswith='test')),
                    UniqueConstraint(name='base_unique_constraint_condition',
                                     fields=['int_field1', 'char_field1'],
                                     condition=Q(int_field1__gte=10)),
                    UniqueConstraint(name='base_unique_constraint_plain',
                                     fields=['int_field1', 'char_field1']),
                    UniqueConstraint(name='new_unique_constraint',
                                     fields=['int_field2', 'int_field1']),
                    CheckConstraint(name='new_check_constraint',
                                    check=Q(int_field1__gte=100)),
                ]

        self.set_base_model(ChangeMetaConstraintsBaseModel)
        self.perform_evolution_tests(
            dest_model=DestModel,
            evolutions=[
                ChangeMeta(
                    'TestModel',
                    'constraints',
                    [
                        {
                            'type': CheckConstraint,
                            'name': 'base_check_constraint',
                            'check': Q(char_field1__startswith='test'),
                        },
                        {
                            'type': UniqueConstraint,
                            'name': 'base_unique_constraint_condition',
                            'fields': ('int_field1', 'char_field1'),
                            'condition': Q(int_field1__gte=10),
                        },
                        {
                            'type': UniqueConstraint,
                            'name': 'base_unique_constraint_plain',
                            'fields': ('int_field1', 'char_field1'),
                        },
                        {
                            'type': UniqueConstraint,
                            'name': 'new_unique_constraint',
                            'fields': ('int_field2', 'int_field1'),
                        },
                        {
                            'type': CheckConstraint,
                            'name': 'new_check_constraint',
                            'check': Q(int_field1__gte=100),
                        },
                    ])
            ],
            diff_text=self.DIFF_TEXT,
            expected_hint=[
                "ChangeMeta('TestModel', 'constraints',"
                " [{'check': models.Q(char_field1__startswith='test'),"
                " 'name': 'base_check_constraint',"
                " 'type': models.CheckConstraint},"
                " {'condition': models.Q(int_field1__gte=10),"
                " 'fields': ('int_field1', 'char_field1'),"
                " 'name': 'base_unique_constraint_condition',"
                " 'type': models.UniqueConstraint},"
                " {'fields': ('int_field1', 'char_field1'),"
                " 'name': 'base_unique_constraint_plain',"
                " 'type': models.UniqueConstraint},"
                " {'fields': ('int_field2', 'int_field1'),"
                " 'name': 'new_unique_constraint',"
                " 'type': models.UniqueConstraint},"
                " {'check': models.Q(int_field1__gte=100),"
                " 'name': 'new_check_constraint',"
                " 'type': models.CheckConstraint}])"
            ],
            sql_name='append_list')

    def test_removing(self):
        """Testing ChangeMeta(constraints) and removing property"""
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

        self.set_base_model(ChangeMetaConstraintsBaseModel)
        self.perform_evolution_tests(
            dest_model=DestModel,
            evolutions=[
                ChangeMeta('TestModel', 'constraints', [])
            ],
            diff_text=self.DIFF_TEXT,
            expected_hint=[
                "ChangeMeta('TestModel', 'constraints', [])"
            ],
            sql_name='removing')


class ChangeMetaDbTableCommentTests(BaseChangeMetaTestCase):
    """Unit tests for ChangeMeta with db_table_comment.

    Version Added:
        2.3
    """

    sql_mapping_key = 'change_meta_db_table_comment'

    DIFF_TEXT = (
        "In model tests.TestModel:\n"
        "    Meta property 'db_table_comment' has changed"
    )

    @classmethod
    @requires_change_meta_field('db_table_comment')
    def setUpClass(cls):
        super(ChangeMetaDbTableCommentTests, cls).setUpClass()

    def test_setting_from_none(self):
        """Testing ChangeMeta(db_table_comment) and setting from None"""
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                db_table_comment = 'New comment!'

        self.set_base_model(ChangeMetaPlainBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel',
                           'db_table_comment',
                           'New comment!')
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'db_table_comment', 'New comment!')",
            ],
            'setting_from_none')

    def test_replace(self):
        """Testing ChangeMeta(db_table_comment) and replacing a comment"""
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                db_table_comment = 'New comment!'

        self.set_base_model(ChangeMetaDbTableCommentBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel',
                           'db_table_comment',
                           'New comment!')
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'db_table_comment', 'New comment!')",
            ],
            'replace')

    def test_unsetting(self):
        """Testing ChangeMeta(db_table_comment) and unsetting a comment"""
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                db_table_comment = None

        self.set_base_model(ChangeMetaDbTableCommentBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta('TestModel',
                           'db_table_comment',
                           None),
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'db_table_comment', None)",
            ],
            'unset')


class ChangeMetaIndexesTests(BaseChangeMetaTestCase):
    """Unit tests for ChangeMeta with indexes."""

    sql_mapping_key = 'indexes'

    DIFF_TEXT = (
        "In model tests.TestModel:\n"
        "    Meta property 'indexes' has changed"
    )

    @classmethod
    @requires_meta_indexes
    def setUpClass(cls):
        super(ChangeMetaIndexesTests, cls).setUpClass()

    def test_keeping_empty(self):
        """Testing ChangeMeta(indexes) and keeping list empty"""
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
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
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
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

    @requires_index_feature('condition')
    def test_setting_from_empty_with_condition(self):
        """Testing ChangeMeta(indexes) and setting to valid list with
        Index(condition=...)
        """
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                indexes = [
                    Index(condition=Q(int_field2__gte=10),
                          fields=['int_field1'],
                          name='my_index'),
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
                            'condition': Q(int_field2__gte=10),
                            'fields': ['int_field1'],
                            'name': 'my_index',
                        },
                    ])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'indexes',"
                " [{'condition': models.Q(int_field2__gte=10),"
                " 'fields': ['int_field1'],"
                " 'name': 'my_index'}])"
            ],
            'setting_from_empty_with_condition')

    @requires_index_feature('db_tablespace')
    def test_setting_from_empty_with_db_tablespace(self):
        """Testing ChangeMeta(indexes) and setting to valid list with
        Index(db_tablespace=...)
        """
        # Tablespaces aren't supported on all databases. If we have one for
        # the evolver, use it. Otherwise, fall back on a custom value (which
        # shouldn't be used in that case outside of signature data).
        tablespace = \
            get_default_tablespace(self.default_database_name) or 'myspace'

        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                indexes = [
                    Index(db_tablespace=tablespace,
                          fields=['int_field1']),
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
                            'db_tablespace': tablespace,
                            'fields': ['int_field1'],
                        },
                    ])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'indexes',"
                " [{'db_tablespace': '%s',"
                " 'fields': ['int_field1']}])"
                % tablespace
            ],
            'setting_from_empty_with_db_tablespace')

    @requires_index_feature('expressions')
    def test_setting_from_empty_with_expressions(self):
        """Testing ChangeMeta(indexes) and setting to valid list with
        Index(*expressions)
        """
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                indexes = [
                    Index(F('int_field1') + F('int_field2'),
                          name='my_index'),
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
                            'expressions': (
                                F('int_field1') + F('int_field2'),
                            ),
                            'name': 'my_index',
                        },
                    ])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'indexes',"
                " [{'expressions': (models.F('int_field1') +"
                " models.F('int_field2'),),"
                " 'name': 'my_index'}])"
            ],
            'setting_from_empty_with_expressions')

    @requires_index_feature('include')
    def test_setting_from_empty_with_include(self):
        """Testing ChangeMeta(indexes) and setting to valid list with
        Index(include=...)
        """
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                indexes = [
                    Index(fields=['int_field1'],
                          include=['char_field1', 'char_field2'],
                          name='my_index'),
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
                            'include': ('char_field1', 'char_field2'),
                            'name': 'my_index',
                        },
                    ])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'indexes',"
                " [{'fields': ['int_field1'],"
                " 'include': ['char_field1', 'char_field2'],"
                " 'name': 'my_index'}])"
            ],
            'setting_from_empty_with_include')

    @requires_index_feature('opclasses')
    def test_setting_from_empty_with_opclasses(self):
        """Testing ChangeMeta(indexes) and setting to valid list with
        Index(opclasses=...)
        """
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                indexes = [
                    Index(fields=['char_field1'],
                          name='my_index',
                          opclasses=['text_pattern_ops']),
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
                            'fields': ['char_field1'],
                            'name': 'my_index',
                            'opclasses': ['text_pattern_ops'],
                        },
                    ])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'indexes',"
                " [{'fields': ['char_field1'],"
                " 'name': 'my_index',"
                " 'opclasses': ['text_pattern_ops']}])"
            ],
            'setting_from_empty_with_opclasses')

    @requires_index_feature('condition')
    def test_replace_condition(self):
        """Testing ChangeMeta(indexes) and replacing condition"""
        class ChangeMetaIndexesConditionBaseModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                indexes = [
                    Index(condition=Q(int_field1__gte=10),
                          fields=['int_field1'],
                          name='my_index'),
                ]

        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                indexes = [
                    Index(condition=Q(int_field2__lte=20),
                          fields=['int_field1'],
                          name='my_index'),
                ]

        self.set_base_model(ChangeMetaIndexesConditionBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta(
                    'TestModel',
                    'indexes',
                    [
                        {
                            'condition': Q(int_field2__lte=20),
                            'fields': ['int_field1'],
                            'name': 'my_index',
                        },
                    ])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'indexes',"
                " [{'condition': models.Q(int_field2__lte=20),"
                " 'fields': ['int_field1'],"
                " 'name': 'my_index'}])"
            ],
            'replace_condition')

    @requires_index_feature('db_tablespace')
    def test_replace_db_tablespace(self):
        """Testing ChangeMeta(indexes) and replacing db_tablespace"""
        # Tablespaces aren't supported on all databases. If we have one for
        # the evolver, use it. Otherwise, fall back on a custom value (which
        # shouldn't be used in that case outside of signature data).
        tablespace = \
            get_default_tablespace(self.default_database_name) or 'myspace'

        class ChangeMetaIndexesTableSpaceBaseModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                indexes = [
                    Index(fields=['int_field1'],
                          name='my_index'),
                ]

        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                indexes = [
                    Index(db_tablespace=tablespace,
                          fields=['int_field1'],
                          name='my_index'),
                ]

        self.set_base_model(ChangeMetaIndexesTableSpaceBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta(
                    'TestModel',
                    'indexes',
                    [
                        {
                            'db_tablespace': tablespace,
                            'fields': ['int_field1'],
                            'name': 'my_index',
                        },
                    ])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'indexes',"
                " [{'db_tablespace': '%s',"
                " 'fields': ['int_field1'],"
                " 'name': 'my_index'}])"
                % tablespace
            ],
            'replace_db_tablespace')

    @requires_index_feature('expressions')
    def test_replace_expression(self):
        """Testing ChangeMeta(indexes) and replacing expressions"""
        class ChangeMetaIndexesExpressionBaseModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                indexes = [
                    Index(F('int_field1') + F('int_field2'),
                          name='my_index'),
                ]

        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                indexes = [
                    Index(F('int_field2') - F('int_field1'),
                          name='my_index'),
                ]

        self.set_base_model(ChangeMetaIndexesExpressionBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta(
                    'TestModel',
                    'indexes',
                    [
                        {
                            'expressions': (F('int_field2') -
                                            F('int_field1'),),
                            'name': 'my_index',
                        },
                    ])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'indexes',"
                " [{'expressions': (models.F('int_field2') -"
                " models.F('int_field1'),),"
                " 'name': 'my_index'}])"
            ],
            'replace_expressions')

    @requires_index_feature('include')
    def test_replace_include(self):
        """Testing ChangeMeta(indexes) and replacing include"""
        class ChangeMetaIndexesIncludeBaseModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                indexes = [
                    Index(fields=['int_field1'],
                          include=['int_field2', 'char_field1'],
                          name='my_index'),
                ]

        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                indexes = [
                    Index(fields=['int_field1'],
                          include=['char_field2', 'char_field1'],
                          name='my_index'),
                ]

        self.set_base_model(ChangeMetaIndexesIncludeBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta(
                    'TestModel',
                    'indexes',
                    [
                        {
                            'fields': ['int_field1'],
                            'include': ['char_field2', 'char_field1'],
                            'name': 'my_index',
                        },
                    ])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'indexes',"
                " [{'fields': ['int_field1'],"
                " 'include': ['char_field2', 'char_field1'],"
                " 'name': 'my_index'}])"
            ],
            'replace_include')

    @requires_index_feature('opclasses')
    def test_replace_opclasses(self):
        """Testing ChangeMeta(indexes) and replacing opclasses"""
        class ChangeMetaIndexesOpclassesBaseModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                indexes = [
                    Index(fields=['char_field1'],
                          opclasses=['varchar_pattern_ops'],
                          name='my_index'),
                ]

        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                indexes = [
                    Index(fields=['char_field1'],
                          opclasses=['text_pattern_ops'],
                          name='my_index'),
                ]

        self.set_base_model(ChangeMetaIndexesOpclassesBaseModel)
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeMeta(
                    'TestModel',
                    'indexes',
                    [
                        {
                            'fields': ['char_field1'],
                            'name': 'my_index',
                            'opclasses': ['text_pattern_ops'],
                        },
                    ])
            ],
            self.DIFF_TEXT,
            [
                "ChangeMeta('TestModel', 'indexes',"
                " [{'fields': ['char_field1'],"
                " 'name': 'my_index',"
                " 'opclasses': ['text_pattern_ops']}])"
            ],
            'replace_opclasses')

    def test_replace_list(self):
        """Testing ChangeMeta(indexes) and replacing list"""
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
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
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
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
        class DestModel(BaseTestModel):
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
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
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


class ChangeMetaIndexTogetherTests(BaseChangeMetaTestCase):
    """Unit tests for ChangeMeta with index_together."""

    sql_mapping_key = 'index_together'

    DIFF_TEXT = (
        "In model tests.TestModel:\n"
        "    Meta property 'index_together' has changed"
    )

    @classmethod
    @requires_meta_index_together
    def setUpClass(cls):
        super(ChangeMetaIndexTogetherTests, cls).setUpClass()

    def test_keeping_empty(self):
        """Testing ChangeMeta(index_together) and keeping list empty"""
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
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
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
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
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
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
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
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
        class DestModel(BaseTestModel):
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
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
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


class ChangeMetaUniqueTogetherTests(BaseChangeMetaTestCase):
    """Unit tests for ChangeMeta with unique_together."""

    sql_mapping_key = 'unique_together'

    DIFF_TEXT = (
        "In model tests.TestModel:\n"
        "    Meta property 'unique_together' has changed"
    )

    def test_keeping_empty(self):
        """Testing ChangeMeta(unique_together) and keeping list empty"""
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
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
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
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
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
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
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
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
        class DestModel(BaseTestModel):
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
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
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
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
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
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                unique_together = [('int_field1', 'char_field1')]

        self.set_base_model(ChangeMetaPlainBaseModel)

        # Pretend this is an older signature with the same unique_together.
        model_sig = (
            self.start_sig
            .get_app_sig('tests')
            .get_model_sig('TestModel')
        )
        model_sig.unique_together = DestModel._meta.unique_together
        model_sig._unique_together_applied = False

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
        class DestModel(BaseTestModel):
            int_field1 = models.IntegerField()
            int_field2 = models.IntegerField()
            char_field1 = models.CharField(max_length=20)
            char_field2 = models.CharField(max_length=40)

            class Meta(BaseTestModel.Meta):
                unique_together = [('int_field1', 'char_field1')]

        self.set_base_model(ChangeMetaUniqueTogetherBaseModel)

        # Pretend this is an older signature with the same unique_together.
        model_sig = (
            self.start_sig
            .get_app_sig('tests')
            .get_model_sig('TestModel')
        )
        model_sig._unique_together_applied = False

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

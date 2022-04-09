"""Unit tests for django_evolution.utils.models."""

from __future__ import unicode_literals

from django.db import DEFAULT_DB_ALIAS, models

from django_evolution.compat.models import get_remote_field
from django_evolution.db.state import DatabaseState
from django_evolution.tests.base_test_case import TestCase
from django_evolution.tests.models import BaseTestModel
from django_evolution.tests.utils import register_models
from django_evolution.utils.models import (clear_model_rel_tree,
                                           get_model_rel_tree,
                                           iter_model_fields,
                                           iter_non_m2m_reverse_relations,
                                           walk_model_tree)


class UtilsModelsAnchor(BaseTestModel):
    value = models.IntegerField()


class UtilsModelsTestModel1(BaseTestModel):
    test1_fkey_field = models.ForeignKey(UtilsModelsAnchor,
                                         related_name='reverse_fkey',
                                         on_delete=models.CASCADE)
    test1_m2m_field = models.ManyToManyField(UtilsModelsAnchor,
                                             related_name='reverse_m2m')
    test1_o2o_field = models.OneToOneField(UtilsModelsAnchor,
                                           related_name='reverse_o2o',
                                           on_delete=models.CASCADE)


class UtilsModelsTestModel2(BaseTestModel):
    test2_fkey_field = models.ForeignKey(UtilsModelsTestModel1,
                                         on_delete=models.CASCADE)


class UtilsModelsTestChildModel(UtilsModelsTestModel1):
    pass


class UtilsTests(TestCase):
    """Unit tests for django_evolution.utils.models."""

    def setUp(self):
        super(UtilsTests, self).setUp()

        register_models(
            database_state=DatabaseState(DEFAULT_DB_ALIAS),
            models=[
                ('UtilsModelsAnchor', UtilsModelsAnchor),
                ('UtilsModelsTestModel1', UtilsModelsTestModel1),
                ('UtilsModelsTestModel2', UtilsModelsTestModel2),
                ('UtilsModelsTestChildModel', UtilsModelsTestChildModel),
            ],
            new_app_label='tests')

    def tearDown(self):
        super(UtilsTests, self).tearDown()

        clear_model_rel_tree()

    def test_get_model_rel_tree(self):
        """Testing get_model_rel_tree"""
        rel_tree = get_model_rel_tree()

        self.assertIn('tests_utilsmodelsanchor', rel_tree)

        m2m_field = UtilsModelsTestModel1._meta.get_field('test1_m2m_field')
        m2m_through = get_remote_field(m2m_field).through

        self.assertEqual(
            set(rel_tree['tests_utilsmodelsanchor']),
            {
                UtilsModelsTestModel1._meta.get_field('test1_fkey_field'),
                UtilsModelsTestModel1._meta.get_field('test1_o2o_field'),
                m2m_field,
                m2m_through._meta.get_field('utilsmodelsanchor'),
            })

    def test_iter_model_fields_with_include_forward_fields(self):
        """Testing iter_model_fields with include_forward_fields=True"""
        fields = set(iter_model_fields(UtilsModelsTestModel1,
                                       include_forward_fields=True))

        self.assertEqual(
            fields,
            {
                UtilsModelsTestModel1._meta.get_field('id'),
                UtilsModelsTestModel1._meta.get_field('test1_fkey_field'),
                UtilsModelsTestModel1._meta.get_field('test1_m2m_field'),
                UtilsModelsTestModel1._meta.get_field('test1_o2o_field'),
            })

    def test_iter_model_fields_with_include_reverse_fields(self):
        """Testing iter_model_fields with include_reverse_fields=True"""
        fields = set(iter_model_fields(UtilsModelsTestModel1,
                                       include_forward_fields=False,
                                       include_reverse_fields=True))

        self.assertEqual(
            fields,
            {
                get_remote_field(UtilsModelsTestModel2._meta.get_field(
                    'test2_fkey_field')),
                get_remote_field(UtilsModelsTestChildModel._meta.get_field(
                    'utilsmodelstestmodel1_ptr')),
            })

    def test_iter_model_fields_with_include_hidden_fields(self):
        """Testing iter_model_fields with include_reverse_fields=True"""
        fields = set(iter_model_fields(UtilsModelsTestModel1,
                                       include_forward_fields=False,
                                       include_reverse_fields=True,
                                       include_hidden_fields=True))

        test1_m2m_field = \
            UtilsModelsTestModel1._meta.get_field('test1_m2m_field')
        test1_m2m_field_through = get_remote_field(test1_m2m_field).through

        self.assertEqual(
            fields,
            {
                get_remote_field(test1_m2m_field_through._meta.get_field(
                    'utilsmodelstestmodel1')),
                get_remote_field(UtilsModelsTestModel2._meta.get_field(
                    'test2_fkey_field')),
                get_remote_field(UtilsModelsTestChildModel._meta.get_field(
                    'utilsmodelstestmodel1_ptr')),
            })

    def test_iter_model_fields_with_include_parent_models(self):
        """Testing iter_model_fields with include_parent_models=True"""
        fields = set(iter_model_fields(UtilsModelsTestChildModel,
                                       include_parent_models=True))

        self.assertEqual(
            fields,
            {
                UtilsModelsTestChildModel._meta.get_field('id'),
                UtilsModelsTestChildModel._meta.get_field(
                    'utilsmodelstestmodel1_ptr'),
                UtilsModelsTestChildModel._meta.get_field('test1_fkey_field'),
                UtilsModelsTestChildModel._meta.get_field('test1_m2m_field'),
                UtilsModelsTestChildModel._meta.get_field('test1_o2o_field'),
            })

    def test_iter_non_m2m_reverse_relations(self):
        """Testing iter_non_m2m_reverse_relations"""
        rels = set(iter_non_m2m_reverse_relations(
            UtilsModelsTestModel1._meta.get_field('id')))

        test1_m2m_field = \
            UtilsModelsTestModel1._meta.get_field('test1_m2m_field')
        test1_m2m_field_through = get_remote_field(test1_m2m_field).through

        self.assertEqual(
            rels,
            {
                get_remote_field(test1_m2m_field_through._meta.get_field(
                    'utilsmodelstestmodel1')),
                get_remote_field(UtilsModelsTestModel2._meta.get_field(
                    'test2_fkey_field')),
                get_remote_field(UtilsModelsTestChildModel._meta.get_field(
                    'utilsmodelstestmodel1_ptr')),
            })

    def test_iter_non_m2m_reverse_relations_with_non_reffed_field(self):
        """Testing iter_non_m2m_reverse_relations with non-referenced field"""
        rels = list(iter_non_m2m_reverse_relations(
            UtilsModelsTestModel1._meta.get_field('test1_fkey_field')))

        self.assertEqual(rels, [])

    def test_walk_model_tree(self):
        """Testing walk_model_tree"""
        self.assertEqual(list(walk_model_tree(UtilsModelsTestChildModel)),
                         [UtilsModelsTestChildModel, UtilsModelsTestModel1])

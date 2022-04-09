"""Unit tests for django_evolution.compat.models."""

from __future__ import unicode_literals

from django.db import DEFAULT_DB_ALIAS, models
from django.db.models.fields import related

from django_evolution.compat.models import (get_field_is_many_to_many,
                                            get_field_is_relation,
                                            get_rel_target_field,
                                            get_remote_field,
                                            get_remote_field_model,
                                            get_remote_field_related_model)
from django_evolution.db.state import DatabaseState
from django_evolution.tests.base_test_case import TestCase
from django_evolution.tests.models import BaseTestModel
from django_evolution.tests.utils import register_models


class CompatModelsAnchor(BaseTestModel):
    value = models.IntegerField()


class CompatModelsTestModel(BaseTestModel):
    fkey_field = models.ForeignKey(CompatModelsAnchor,
                                   related_name='reverse_fkey',
                                   on_delete=models.CASCADE)
    m2m_field = models.ManyToManyField(CompatModelsAnchor,
                                       related_name='reverse_m2m')
    o2o_field = models.OneToOneField(CompatModelsAnchor,
                                     related_name='reverse_o2o',
                                     on_delete=models.CASCADE)


class BaseRelationFieldsTestCase(TestCase):
    def setUp(self):
        super(BaseRelationFieldsTestCase, self).setUp()

        register_models(
            database_state=DatabaseState(DEFAULT_DB_ALIAS),
            models=[
                ('CompatModelsTestModel', CompatModelsTestModel),
                ('CompatModelsAnchor', CompatModelsAnchor),
            ],
            new_app_label='tests')


class GetFieldIsManyToManyTests(BaseRelationFieldsTestCase):
    """Unit tests for get_field_is_many_to_many."""

    def test_with_many_to_many_field(self):
        """Testing get_field_is_many_to_many with ManyToManyField"""
        self.assertTrue(get_field_is_many_to_many(
            CompatModelsTestModel._meta.get_field('m2m_field')))

    def test_with_many_to_many_field_rel(self):
        """Testing get_field_is_many_to_many with ManyToManyField relation"""
        rel = get_remote_field(
            CompatModelsTestModel._meta.get_field('m2m_field'))

        self.assertIsInstance(rel, related.ManyToManyRel)
        self.assertTrue(get_field_is_many_to_many(rel))

    def test_with_non_many_to_many_field(self):
        """Testing get_field_is_many_to_many with non-ManyToManyField"""
        self.assertFalse(get_field_is_many_to_many(
            CompatModelsTestModel._meta.get_field('fkey_field')))
        self.assertFalse(get_field_is_many_to_many(
            CompatModelsTestModel._meta.get_field('o2o_field')))


class GetFieldIsRelationTests(BaseRelationFieldsTestCase):
    """Unit tests for get_field_is_relation."""

    def test_with_foreign_key(self):
        """Testing get_field_is_relation with ForeignKey"""
        self.assertTrue(get_field_is_relation(
            CompatModelsTestModel._meta.get_field('fkey_field')))

    def test_with_foreign_key_rel(self):
        """Testing get_field_is_relation with ForeignKey relation"""
        rel = get_remote_field(
            CompatModelsTestModel._meta.get_field('fkey_field'))

        self.assertIsInstance(rel, related.ManyToOneRel)
        self.assertTrue(get_field_is_relation(rel))

    def test_with_many_to_many_field(self):
        """Testing get_field_is_relation with ManyToManyField"""
        self.assertTrue(get_field_is_relation(
            CompatModelsTestModel._meta.get_field('m2m_field')))

    def test_with_many_to_many_field_rel(self):
        """Testing get_field_is_relation with ManyToManyField relation"""
        rel = get_remote_field(
            CompatModelsTestModel._meta.get_field('m2m_field'))

        self.assertIsInstance(rel, related.ManyToManyRel)
        self.assertTrue(get_field_is_relation(rel))

    def test_with_one_to_one_field(self):
        """Testing get_field_is_relation with OneToOneField"""
        self.assertTrue(get_field_is_relation(
            CompatModelsTestModel._meta.get_field('o2o_field')))

    def test_with_one_to_one_field_rel(self):
        """Testing get_field_is_relation with OneToOneField relation"""
        rel = get_remote_field(
            CompatModelsTestModel._meta.get_field('o2o_field'))

        self.assertIsInstance(rel, related.ManyToOneRel)
        self.assertTrue(get_field_is_relation(rel))

    def test_with_non_rel_field(self):
        """Testing get_field_is_relation with non-relation field"""
        # Test with a normal field.
        self.assertFalse(get_field_is_relation(
            CompatModelsAnchor._meta.get_field('value')))

        # Test with a primary key.
        self.assertFalse(get_field_is_relation(
            CompatModelsAnchor._meta.get_field('id')))


class GetRelTargetFieldTests(BaseRelationFieldsTestCase):
    """Unit tests for get_rel_target_field."""

    # Note that this function inherently doesn't work with other types of
    # fields or the other side of a relation.
    def test_with_foreign_key(self):
        """Testing get_rel_target_field with ForeignKey"""
        fkey_field = CompatModelsTestModel._meta.get_field('fkey_field')

        self.assertIs(get_rel_target_field(fkey_field),
                      CompatModelsAnchor._meta.get_field('id'))


class GetRemoteFieldTests(BaseRelationFieldsTestCase):
    """Unit tests for get_remote_field."""

    def test_with_foreign_key(self):
        """Testing get_remote_field with ForeignKey"""
        rel = get_remote_field(
            CompatModelsTestModel._meta.get_field('fkey_field'))

        self.assertIsInstance(rel, related.ManyToOneRel)

    def test_with_foreign_key_rel(self):
        """Testing get_remote_field with ForeignKey relation"""
        field = CompatModelsTestModel._meta.get_field('fkey_field')
        rel = get_remote_field(get_remote_field(field))

        self.assertIs(rel, field)

    def test_with_many_to_many_field(self):
        """Testing get_remote_field with ManyToManyField"""
        rel = get_remote_field(
            CompatModelsTestModel._meta.get_field('m2m_field'))

        self.assertIsInstance(rel, related.ManyToManyRel)

    def test_with_many_to_many_field_rel(self):
        """Testing get_remote_field with ManyToManyField relation"""
        field = CompatModelsTestModel._meta.get_field('m2m_field')
        rel = get_remote_field(get_remote_field(field))

        self.assertIs(rel, field)

    def test_with_one_to_one_field(self):
        """Testing get_remote_field with OneToOneField"""
        rel = get_remote_field(
            CompatModelsTestModel._meta.get_field('o2o_field'))

        self.assertIsInstance(rel, related.OneToOneRel)

    def test_with_one_to_one_field_rel(self):
        """Testing get_remote_field with OneToOneField relation"""
        field = CompatModelsTestModel._meta.get_field('o2o_field')
        rel = get_remote_field(get_remote_field(field))

        self.assertIs(rel, field)


class GetRemoteFieldModelTests(BaseRelationFieldsTestCase):
    """Unit tests for get_remote_field_model."""

    def test_with_foreign_key(self):
        """Testing get_remote_field_model with ForeignKey"""
        model = get_remote_field_model(
            CompatModelsTestModel._meta.get_field('fkey_field'))

        self.assertIs(model, CompatModelsTestModel)

    def test_with_foreign_key_rel(self):
        """Testing get_remote_field_model with ForeignKey relation"""
        field = CompatModelsTestModel._meta.get_field('fkey_field')
        model = get_remote_field_model(get_remote_field(field))

        self.assertIs(model, CompatModelsAnchor)

    def test_with_many_to_many_field(self):
        """Testing get_remote_field_model with ManyToManyField"""
        model = get_remote_field_model(
            CompatModelsTestModel._meta.get_field('m2m_field'))

        self.assertIs(model, CompatModelsTestModel)

    def test_with_many_to_many_field_rel(self):
        """Testing get_remote_field_model with ManyToManyField relation"""
        field = CompatModelsTestModel._meta.get_field('m2m_field')
        model = get_remote_field_model(get_remote_field(field))

        self.assertIs(model, CompatModelsAnchor)

    def test_with_one_to_one_field(self):
        """Testing get_remote_field_model with OneToOneField"""
        model = get_remote_field_model(
            CompatModelsTestModel._meta.get_field('o2o_field'))

        self.assertIs(model, CompatModelsTestModel)

    def test_with_one_to_one_field_rel(self):
        """Testing get_remote_field_model with OneToOneField relation"""
        field = CompatModelsTestModel._meta.get_field('o2o_field')
        model = get_remote_field_model(get_remote_field(field))

        self.assertIs(model, CompatModelsAnchor)


class GetRemoteFieldRelatedModelTests(BaseRelationFieldsTestCase):
    """Unit tests for get_remote_field_related_model."""

    def test_with_foreign_key(self):
        """Testing get_remote_field_related_model with ForeignKey"""
        model = get_remote_field_related_model(
            CompatModelsTestModel._meta.get_field('fkey_field'))

        self.assertIs(model, CompatModelsAnchor)

    def test_with_foreign_key_rel(self):
        """Testing get_remote_field_related_model with ForeignKey relation"""
        field = CompatModelsTestModel._meta.get_field('fkey_field')
        model = get_remote_field_related_model(get_remote_field(field))

        self.assertIs(model, CompatModelsTestModel)

    def test_with_many_to_many_field(self):
        """Testing get_remote_field_related_model with ManyToManyField"""
        model = get_remote_field_related_model(
            CompatModelsTestModel._meta.get_field('m2m_field'))

        self.assertIs(model, CompatModelsAnchor)

    def test_with_many_to_many_field_rel(self):
        """Testing get_remote_field_related_model with ManyToManyField
        relation
        """
        field = CompatModelsTestModel._meta.get_field('m2m_field')
        model = get_remote_field_related_model(get_remote_field(field))

        self.assertIs(model, CompatModelsTestModel)

    def test_with_one_to_one_field(self):
        """Testing get_remote_field_related_model with OneToOneField"""
        model = get_remote_field_related_model(
            CompatModelsTestModel._meta.get_field('o2o_field'))

        self.assertIs(model, CompatModelsAnchor)

    def test_with_one_to_one_field_rel(self):
        """Testing get_remote_field_related_model with OneToOneField relation
        """
        field = CompatModelsTestModel._meta.get_field('o2o_field')
        model = get_remote_field_related_model(get_remote_field(field))

        self.assertIs(model, CompatModelsTestModel)

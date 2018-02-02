"""Unit tests for the signature-related functionality."""

from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.utils import DEFAULT_DB_ALIAS
from django.utils import six

from django_evolution.compat.apps import get_app
from django_evolution.compat.models import GenericForeignKey, GenericRelation
from django_evolution.models import Evolution
from django_evolution.signature import (create_app_sig, create_field_sig,
                                        create_model_sig)
from django_evolution.tests.base_test_case import EvolutionTestCase


class SignatureAnchor1(models.Model):
    value = models.IntegerField()


class SignatureAnchor2(models.Model):
    value = models.IntegerField()


class SignatureAnchor3(models.Model):
    value = models.IntegerField()

    # Host a generic key here, too.
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey('content_type', 'object_id')


class SignatureFullModel(models.Model):
    char_field = models.CharField(max_length=20)
    int_field = models.IntegerField()
    null_field = models.IntegerField(null=True, db_column='size_column')
    id_card = models.IntegerField(unique=True, db_index=True)
    dec_field = models.DecimalField(max_digits=10, decimal_places=4)
    ref1 = models.ForeignKey(SignatureAnchor1)
    ref2 = models.ForeignKey(SignatureAnchor1, related_name='other_sigmodel')
    ref3 = models.ForeignKey(SignatureAnchor2, db_column='value',
                             db_index=True)
    ref4 = models.ForeignKey('self')
    ref5 = models.ManyToManyField(SignatureAnchor3)
    ref6 = models.ManyToManyField(SignatureAnchor3,
                                  related_name='other_sigmodel')
    ref7 = models.ManyToManyField('self')

    # Plus a generic foreign key - the Generic itself should be ignored.
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    # Plus a generic relation, which should be ignored.
    generic = GenericRelation(SignatureAnchor3)


class SignatureDefaultsModel(models.Model):
    char_field = models.CharField()
    dec_field = models.DecimalField()
    m2m_field = models.ManyToManyField('self')
    fkey_field = models.ForeignKey(SignatureAnchor1)


class SignatureParentModel(models.Model):
    parent_field = models.CharField(max_length=20)


class SignatureChildModel(SignatureParentModel):
    child_field = models.CharField(max_length=20)


class BaseSignatureTestCase(EvolutionTestCase):
    """Base class for signature-related unit tests."""

    default_base_model = SignatureFullModel
    default_extra_models = [
        ('Anchor1', SignatureAnchor1),
        ('Anchor2', SignatureAnchor2),
        ('Anchor3', SignatureAnchor3),
        ('DefaultsModel', SignatureDefaultsModel),
        ('ChildModel', SignatureChildModel),
        ('ParentModel', SignatureParentModel),
    ]


class ApplicationSignatureTests(BaseSignatureTestCase):
    """Unit tests for create_app_sig."""

    def test_create_app_sig(self):
        """Testing create_app_sig"""
        app_sig = create_app_sig(get_app('django_evolution'),
                                 database=DEFAULT_DB_ALIAS)

        model_names = set(six.iterkeys(app_sig))

        for model_name in ('Evolution', 'Version'):
            self.assertIn(model_name, model_names)

            model_sig = app_sig[model_name]
            self.assertIn('meta', model_sig)
            self.assertIn('fields', model_sig)

    def test_create_app_sig_with_router(self):
        """Testing create_app_sig with router.allow_syncdb/allow_migrate_model
        """
        class TestRouter(object):
            def allow_syncdb(self, db, model):
                return model is Evolution

            def allow_migrate(self, *args, **hints):
                if 'model' in hints:
                    # Django 1.8+
                    model = hints['model']
                else:
                    # Django 1.7
                    assert len(args) == 2
                    model = args[1]

                return model is Evolution

        with self.override_db_routers([TestRouter()]):
            app_sig = create_app_sig(get_app('django_evolution'),
                                     database=DEFAULT_DB_ALIAS)

        model_names = set(six.iterkeys(app_sig))
        self.assertIn('Evolution', model_names)
        self.assertNotIn('Version', model_names)


class FieldSignatureTests(BaseSignatureTestCase):
    """Unit tests for create_field_sig."""

    def test_create_field_sig(self):
        """Testing create_field_sig"""
        field_sig = \
            create_field_sig(SignatureFullModel._meta.get_field('null_field'))

        self.assertEqual(
            field_sig,
            {
                'db_column': 'size_column',
                'field_type': models.IntegerField,
                'null': True,
            })

    def test_create_field_sig_with_unique(self):
        """Testing create_field_sig with _unique stored as unique"""
        field_sig = \
            create_field_sig(SignatureFullModel._meta.get_field('id_card'))

        self.assertEqual(
            field_sig,
            {
                'db_index': True,
                'field_type': models.IntegerField,
                'unique': True,
            })

    def test_create_field_sig_with_defaults_not_stored(self):
        """Testing create_field_sig with field defaults not stored"""
        meta = SignatureDefaultsModel._meta

        self.assertEqual(
            create_field_sig(meta.get_field('char_field')),
            {
                'field_type': models.CharField,
            })

        self.assertEqual(
            create_field_sig(meta.get_field('dec_field')),
            {
                'field_type': models.DecimalField,
            })

        self.assertEqual(
            create_field_sig(meta.get_field('m2m_field')),
            {
                'field_type': models.ManyToManyField,
                'related_model': 'tests.DefaultsModel',
            })

        self.assertEqual(
            create_field_sig(meta.get_field('fkey_field')),
            {
                'field_type': models.ForeignKey,
                'related_model': 'tests.Anchor1',
            })


class ModelSignatureTests(BaseSignatureTestCase):
    """Unit tests for create_model_sig."""

    def test_create_model_sig(self):
        """Testing create_model_sig"""
        model_sig = create_model_sig(SignatureFullModel)

        self.assertEqual(
            model_sig,
            {
                'fields': {
                    'char_field': {
                        'field_type': models.CharField,
                        'max_length': 20,
                    },
                    'content_type': {
                        'field_type': models.ForeignKey,
                        'related_model': 'contenttypes.ContentType',
                    },
                    'dec_field': {
                        'decimal_places': 4,
                        'field_type': models.DecimalField,
                        'max_digits': 10,
                    },
                    'id': {
                        'field_type': models.AutoField,
                        'primary_key': True,
                    },
                    'id_card': {
                        'db_index': True,
                        'field_type': models.IntegerField,
                        'unique': True,
                    },
                    'int_field': {
                        'field_type': models.IntegerField,
                    },
                    'null_field': {
                        'db_column': 'size_column',
                        'field_type': models.IntegerField,
                        'null': True,
                    },
                    'object_id': {
                        'db_index': True,
                        'field_type': models.PositiveIntegerField,
                    },
                    'ref1': {
                        'field_type': models.ForeignKey,
                        'related_model': 'tests.Anchor1',
                    },
                    'ref2': {
                        'field_type': models.ForeignKey,
                        'related_model': 'tests.Anchor1',
                    },
                    'ref3': {
                        'db_column': 'value',
                        'field_type': models.ForeignKey,
                        'related_model': 'tests.Anchor2',
                    },
                    'ref4': {
                        'field_type': models.ForeignKey,
                        'related_model': 'tests.TestModel',
                    },
                    'ref5': {
                        'field_type': models.ManyToManyField,
                        'related_model': 'tests.Anchor3',
                    },
                    'ref6': {
                        'field_type': models.ManyToManyField,
                        'related_model': 'tests.Anchor3',
                    },
                    'ref7': {
                        'field_type': models.ManyToManyField,
                        'related_model': 'tests.TestModel',
                    },
                },
                'meta': {
                    '__unique_together_applied': True,
                    'db_table': 'tests_testmodel',
                    'db_tablespace': '',
                    'index_together': [],
                    'pk_column': 'id',
                    'unique_together': [],
                },
            })

    def test_create_model_sig_with_subclass(self):
        """Testing create_model_sig with subclass of model"""
        model_sig = create_model_sig(SignatureChildModel)

        self.assertEqual(
            model_sig,
            {
                'fields': {
                    'child_field': {
                        'field_type': models.CharField,
                        'max_length': 20,
                    },
                    'signatureparentmodel_ptr': {
                        'field_type': models.OneToOneField,
                        'primary_key': True,
                        'related_model': 'tests.ParentModel',
                        'unique': True,
                    },
                },
                'meta': {
                    '__unique_together_applied': True,
                    'db_table': 'tests_childmodel',
                    'db_tablespace': '',
                    'index_together': [],
                    'pk_column': 'signatureparentmodel_ptr_id',
                    'unique_together': [],
                },
            })

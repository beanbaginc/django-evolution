"""Unit tests for the signature-related functionality."""

from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.utils import DEFAULT_DB_ALIAS
from django.utils import six
from nose import SkipTest

try:
    # Django >= 1.11
    from django.db.models import Index
except ImportError:
    # Django <= 1.10
    Index = None

from django_evolution.compat.apps import get_app
from django_evolution.compat.models import GenericForeignKey, GenericRelation
from django_evolution.models import Evolution
from django_evolution.signature import (AppSignature, FieldSignature,
                                        IndexSignature, ModelSignature,
                                        ProjectSignature)
from django_evolution.tests.base_test_case import EvolutionTestCase


class SignatureAnchor1(models.Model):
    value = models.IntegerField()


class SignatureAnchor2(models.Model):
    value = models.IntegerField()


class SignatureAnchor3(models.Model):
    value = models.IntegerField()

    # Host a generic key here, too.
    content_type = models.ForeignKey(ContentType,
                                     on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey('content_type', 'object_id')


class SignatureFullModel(models.Model):
    char_field = models.CharField(max_length=20)
    int_field = models.IntegerField()
    null_field = models.IntegerField(null=True, db_column='size_column')
    id_card = models.IntegerField(unique=True, db_index=True)
    dec_field = models.DecimalField(max_digits=10, decimal_places=4)
    ref1 = models.ForeignKey(SignatureAnchor1,
                             on_delete=models.CASCADE)
    ref2 = models.ForeignKey(SignatureAnchor1,
                             related_name='other_sigmodel',
                             on_delete=models.CASCADE)
    ref3 = models.ForeignKey(SignatureAnchor2,
                             db_column='value',
                             db_index=True,
                             on_delete=models.CASCADE)
    ref4 = models.ForeignKey('self',
                             on_delete=models.CASCADE)
    ref5 = models.ManyToManyField(SignatureAnchor3)
    ref6 = models.ManyToManyField(SignatureAnchor3,
                                  related_name='other_sigmodel')
    ref7 = models.ManyToManyField('self')

    # Plus a generic foreign key - the Generic itself should be ignored.
    content_type = models.ForeignKey(ContentType,
                                     on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    # Plus a generic relation, which should be ignored.
    generic = GenericRelation(SignatureAnchor3)


class SignatureDefaultsModel(models.Model):
    char_field = models.CharField()
    dec_field = models.DecimalField()
    m2m_field = models.ManyToManyField('self')
    fkey_field = models.ForeignKey(SignatureAnchor1,
                                   on_delete=models.CASCADE)


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


class ProjectSignatureTests(BaseSignatureTestCase):
    """Unit tests for ProjectSignature."""

    def test_from_database(self):
        """Testing ProjectSignature.from_database"""
        project_sig = ProjectSignature.from_database('default')

        app_ids = set(
            app_sig.app_id
            for app_sig in project_sig.app_sigs
        )

        self.assertIn('contenttypes', app_ids)
        self.assertIn('django_evolution', app_ids)

    def test_deserialize_v1(self):
        """Testing ProjectSignature.deserialize (signature v1)"""
        project_sig = ProjectSignature.deserialize(
            {
                '__version__': 1,
                'app1': {},
                'app2': {},
            },
            sig_version=1)

        self.assertEqual(
            set(
                app_sig.app_id
                for app_sig in project_sig.app_sigs
            ),
            set(['app1', 'app2']))

    def test_add_app(self):
        """Testing ProjectSignature.add_app"""
        project_sig = ProjectSignature()
        project_sig.add_app(get_app('django_evolution'), database='default')

        self.assertEqual(
            [
                app_sig.app_id
                for app_sig in project_sig.app_sigs
            ],
            ['django_evolution'])

    def test_add_app_sig(self):
        """Testing ProjectSignature.add_app_sig"""
        project_sig = ProjectSignature()

        app_sig = AppSignature.from_app(get_app('django_evolution'),
                                        database='default')
        project_sig.add_app_sig(app_sig)

        self.assertEqual(list(project_sig.app_sigs), [app_sig])

    def test_clone(self):
        """Testing ProjectSignature.clone"""
        project_sig = ProjectSignature()

        app_sig = AppSignature.from_app(get_app('django_evolution'),
                                        database='default')
        project_sig.add_app_sig(app_sig)

        cloned_project_sig = project_sig.clone()
        self.assertIsNot(cloned_project_sig, project_sig)
        self.assertEqual(cloned_project_sig, project_sig)

        for cloned_app_sig, app_sig in zip(cloned_project_sig.app_sigs,
                                           project_sig.app_sigs):
            self.assertIsNot(cloned_app_sig, app_sig)
            self.assertEqual(cloned_app_sig, app_sig)

    def test_serialize_v1(self):
        """Testing ProjectSignature.serialize (signature v1)"""
        project_sig = ProjectSignature()
        project_sig.add_app_sig(AppSignature('test_app'))

        self.assertEqual(
            project_sig.serialize(sig_version=1),
            {
                '__version__': 1,
                'test_app': {},
            })


class AppSignatureTests(BaseSignatureTestCase):
    """Unit tests for AppSignature."""

    def test_from_app(self):
        """Testing AppSignature.from_app"""
        app_sig = AppSignature.from_app(get_app('django_evolution'),
                                        database=DEFAULT_DB_ALIAS)
        model_names = set(
            model_sig.model_name
            for model_sig in app_sig.model_sigs
        )

        self.assertEqual(app_sig.app_id, 'django_evolution')
        self.assertIn('Version', model_names)
        self.assertIn('Evolution', model_names)

    def test_deserialize_v1(self):
        """Testing AppSignature.deserialize (signature v1)"""
        app_sig = AppSignature.deserialize(
            'app1',
            {
                'model1': {
                    'meta': {
                        'db_table': 'app1_model1',
                    },
                    'fields': {},
                },
                'model2': {
                    'meta': {
                        'db_table': 'app1_model2',
                    },
                    'fields': {},
                },
            },
            sig_version=1)

        self.assertEqual(app_sig.app_id, 'app1')

        model_sigs = sorted(app_sig.model_sigs,
                            key=lambda sig: sig.model_name)
        self.assertEqual(len(model_sigs), 2)

        model_sig = model_sigs[0]
        self.assertEqual(model_sig.model_name, 'model1')
        self.assertEqual(model_sig.table_name, 'app1_model1')

        model_sig = model_sigs[1]
        self.assertEqual(model_sig.model_name, 'model2')
        self.assertEqual(model_sig.table_name, 'app1_model2')

    def test_add_model(self):
        """Testing AppSignature.add_model"""
        app_sig = AppSignature('django_evolution')
        app_sig.add_model(Evolution)

        self.assertEqual(
            [
                model_sig.model_name
                for model_sig in app_sig.model_sigs
            ],
            ['Evolution'])

    def test_add_model_sig(self):
        """Testing AppSignature.add_model_sig"""
        app_sig = AppSignature('django_evolution')

        model_sig = ModelSignature.from_model(Evolution)
        app_sig.add_model_sig(model_sig)

        self.assertEqual(list(app_sig.model_sigs), [model_sig])

    def test_get_model_sig(self):
        """Testing AppSignature.get_model_sig"""
        app_sig = AppSignature('django_evolution')

        model_sig = ModelSignature.from_model(Evolution)
        app_sig.add_model_sig(model_sig)

        self.assertIs(app_sig.get_model_sig('Evolution'), model_sig)

    def test_clone(self):
        """Testing AppSignature.clone"""
        app_sig = AppSignature.from_app(get_app('django_evolution'),
                                        database=DEFAULT_DB_ALIAS)
        cloned_app_sig = app_sig.clone()

        for cloned_model_sig, model_sig in zip(cloned_app_sig.model_sigs,
                                               app_sig.model_sigs):
            self.assertIsNot(cloned_model_sig, model_sig)
            self.assertEqual(cloned_model_sig, model_sig)

    def test_serialize_v1(self):
        """Testing AppSignature.serialize (signature v1)"""
        app_sig = AppSignature('testapp')
        app_sig.add_model_sig(ModelSignature(model_name='MyModel',
                                             table_name='testapp_mymodel'))

        self.assertEqual(
            app_sig.serialize(sig_version=1),
            {
                'MyModel': {
                    'fields': {},
                    'meta': {
                        'db_table': 'testapp_mymodel',
                        'db_tablespace': None,
                        'indexes': [],
                        'index_together': [],
                        'unique_together': [],
                        'pk_column': None,
                        '__unique_together_applied': False,
                    },
                },
            })

    def test_serialize_v1_with_router(self):
        """Testing AppSignature.serialize (signature v1) with
        router.allow_syncdb/allow_migrate_model
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
            app_sig = AppSignature.from_app(get_app('django_evolution'),
                                            database=DEFAULT_DB_ALIAS)

        model_names = set(six.iterkeys(app_sig.serialize(sig_version=1)))
        self.assertIn('Evolution', model_names)
        self.assertNotIn('Version', model_names)


class FieldSignatureTests(BaseSignatureTestCase):
    """Unit tests for FieldSignature."""

    def test_from_field(self):
        """Testing FieldSignature.from_field"""
        field_sig = FieldSignature.from_field(
            SignatureFullModel._meta.get_field('null_field'))

        self.assertEqual(field_sig.field_name, 'null_field')
        self.assertIs(field_sig.field_type, models.IntegerField)
        self.assertEqual(
            field_sig.field_attrs,
            {
                'null': True,
                'db_column': 'size_column',
            })

    def test_deserialize_v1(self):
        """Testing FieldSignature.deserialize (signature v1)"""
        field_sig = FieldSignature.deserialize(
            'myfield',
            {
                'field_type': models.CharField,
                'null': False,
                'db_column': 'test_column',
            },
            sig_version=1)

        self.assertEqual(field_sig.field_name, 'myfield')
        self.assertIs(field_sig.field_type, models.CharField)
        self.assertEqual(
            field_sig.field_attrs,
            {
                'null': False,
                'db_column': 'test_column',
            })

    def test_get_attr_value(self):
        """Testing FieldSignature.get_attr_value"""
        field_sig = FieldSignature.from_field(
            SignatureFullModel._meta.get_field('null_field'))

        self.assertEqual(field_sig.get_attr_value('db_column'),
                         'size_column')

    def test_get_attr_value_with_not_set_and_use_default_true(self):
        """Testing FieldSignature.get_attr_value with not set and
        use_default=True
        """
        field_sig = FieldSignature.from_field(
            SignatureFullModel._meta.get_field('null_field'))

        self.assertFalse(field_sig.get_attr_value('db_index'))

    def test_get_attr_value_with_not_set_and_use_default_false(self):
        """Testing FieldSignature.get_attr_value with not set and
        use_default=False
        """
        field_sig = FieldSignature.from_field(
            SignatureFullModel._meta.get_field('null_field'))

        self.assertIsNone(field_sig.get_attr_value('db_index',
                                                   use_default=False))

    def test_get_attr_default(self):
        """Testing FieldSignature.get_attr_default"""
        field_sig = FieldSignature.from_field(
            SignatureFullModel._meta.get_field('null_field'))

        self.assertFalse(field_sig.get_attr_default('null'))

    def test_is_attr_value_default(self):
        """Testing FieldSignature.is_attr_value_default"""
        field_sig = FieldSignature.from_field(
            SignatureFullModel._meta.get_field('null_field'))

        self.assertTrue(field_sig.is_attr_value_default('db_index'))
        self.assertFalse(field_sig.is_attr_value_default('null'))

    def test_clone(self):
        """Testing FieldSignature.clone"""
        field_sig = FieldSignature.from_field(
            SignatureFullModel._meta.get_field('null_field'))

        cloned_field_sig = field_sig.clone()
        self.assertIsNot(cloned_field_sig, field_sig)
        self.assertEqual(cloned_field_sig, field_sig)
        self.assertIsNot(cloned_field_sig.field_attrs, field_sig.field_attrs)

    def test_serialize_v1(self):
        """Testing FieldSignature.serialize (signature v1)"""
        field_sig = FieldSignature.from_field(
            SignatureFullModel._meta.get_field('null_field'))

        self.assertEqual(
            field_sig.serialize(sig_version=1),
            {
                'db_column': 'size_column',
                'field_type': models.IntegerField,
                'null': True,
            })

    def test_serialize_v1_with_unique(self):
        """Testing FieldSignature.serialize (signature v1) with _unique
        stored as unique
        """
        field_sig = FieldSignature.from_field(
            SignatureFullModel._meta.get_field('id_card'))

        self.assertEqual(
            field_sig.serialize(sig_version=1),
            {
                'db_index': True,
                'field_type': models.IntegerField,
                'unique': True,
            })

    def test_serialize_v1_with_defaults_not_stored(self):
        """Testing FieldSignature.serialize (signature v1) with field
        defaults not stored
        """
        meta = SignatureDefaultsModel._meta

        field_sig = FieldSignature.from_field(meta.get_field('char_field'))
        self.assertEqual(
            field_sig.serialize(sig_version=1),
            {
                'field_type': models.CharField,
            })

        field_sig = FieldSignature.from_field(meta.get_field('dec_field'))
        self.assertEqual(
            field_sig.serialize(sig_version=1),
            {
                'field_type': models.DecimalField,
            })

        field_sig = FieldSignature.from_field(meta.get_field('m2m_field'))
        self.assertEqual(
            field_sig.serialize(sig_version=1),
            {
                'field_type': models.ManyToManyField,
                'related_model': 'tests.DefaultsModel',
            })

        field_sig = FieldSignature.from_field(meta.get_field('fkey_field'))
        self.assertEqual(
            field_sig.serialize(sig_version=1),
            {
                'field_type': models.ForeignKey,
                'related_model': 'tests.Anchor1',
            })


class ModelSignatureTests(BaseSignatureTestCase):
    """Unit tests for ModelSignature."""

    def test_from_model(self):
        """Testing ModelSignature.from_model"""
        class ModelSignatureFromModelTestModel(models.Model):
            field1 = models.CharField(max_length=100)
            field2 = models.IntegerField(null=True)
            field3 = models.BooleanField()

            class Meta:
                db_table = 'my_table'
                db_tablespace = 'my_tablespace'
                index_together = (('field1', 'field2'),)
                unique_together = (('field2', 'field3'),)

                if Index:
                    indexes = [
                        Index(name='index1', fields=['field1']),
                        Index(name='index2', fields=['field3']),
                    ]

        model_sig = ModelSignature.from_model(ModelSignatureFromModelTestModel)

        self.assertEqual(model_sig.db_tablespace, 'my_tablespace')
        self.assertEqual(model_sig.index_together, [('field1', 'field2')])
        self.assertEqual(model_sig.model_name,
                         'ModelSignatureFromModelTestModel')
        self.assertEqual(model_sig.pk_column, 'id')
        self.assertEqual(model_sig.table_name, 'my_table')
        self.assertEqual(model_sig.unique_together, [('field2', 'field3')])

        field_sigs = list(model_sig.field_sigs)
        self.assertEqual(len(field_sigs), 4)
        self.assertEqual(field_sigs[0].field_name, 'id')
        self.assertEqual(field_sigs[1].field_name, 'field1')
        self.assertEqual(field_sigs[2].field_name, 'field2')
        self.assertEqual(field_sigs[3].field_name, 'field3')

        if Index:
            index_sigs = list(model_sig.index_sigs)
            self.assertEqual(len(index_sigs), 2)

            index_sig = index_sigs[0]
            self.assertEqual(index_sig.name, 'index1')
            self.assertEqual(index_sig.fields, ['field1'])

            index_sig = index_sigs[1]
            self.assertEqual(index_sig.name, 'index2')
            self.assertEqual(index_sig.fields, ['field3'])

    def test_deserialize(self):
        """Testing ModelSignature.deserialize (signature v1)"""
        model_sig = ModelSignature.deserialize(
            'TestModel',
            {
                'meta': {
                    'db_table': 'my_table',
                    'db_tablespace': 'my_tablespace',
                    'index_together': [['field1', 'field2']],
                    'indexes': [
                        {
                            'name': 'index1',
                            'fields': ['field1'],
                        },
                        {
                            'name': 'index2',
                            'fields': ['field2'],
                        },
                    ],
                    'pk_column': 'id',
                    'unique_together': [['field2', 'field3']],
                },
                'fields': {
                    'field1': {
                        'field_type': models.CharField,
                        'max_length': 100,
                    },
                },
            },
            sig_version=1)

        self.assertEqual(model_sig.db_tablespace, 'my_tablespace')
        self.assertEqual(model_sig.index_together, [('field1', 'field2')])
        self.assertEqual(model_sig.model_name, 'TestModel')
        self.assertEqual(model_sig.pk_column, 'id')
        self.assertEqual(model_sig.table_name, 'my_table')
        self.assertEqual(model_sig.unique_together, [('field2', 'field3')])

        field_sigs = list(model_sig.field_sigs)
        self.assertEqual(len(field_sigs), 1)
        self.assertEqual(field_sigs[0].field_name, 'field1')

        if Index:
            index_sigs = list(model_sig.index_sigs)
            self.assertEqual(len(index_sigs), 2)

            index_sig = index_sigs[0]
            self.assertEqual(index_sig.name, 'index1')
            self.assertEqual(index_sig.fields, ['field1'])

            index_sig = index_sigs[1]
            self.assertEqual(index_sig.name, 'index2')
            self.assertEqual(index_sig.fields, ['field2'])

    def test_add_field(self):
        """Testing ModelSignature.add_field"""
        model_sig = ModelSignature(model_name='TestModel',
                                   table_name='testmodel')
        model_sig.add_field(
            SignatureDefaultsModel._meta.get_field('char_field'))

        field_sigs = list(model_sig.field_sigs)
        self.assertEqual(len(field_sigs), 1)

        field_sig = field_sigs[0]
        self.assertEqual(field_sig.field_name, 'char_field')
        self.assertIs(field_sig.field_type, models.CharField)

    def test_add_field_sig(self):
        """Testing ModelSignature.add_field_sig"""
        model_sig = ModelSignature(model_name='TestModel',
                                   table_name='testmodel')
        model_sig.add_field_sig(FieldSignature.from_field(
            SignatureDefaultsModel._meta.get_field('char_field')))

        field_sigs = list(model_sig.field_sigs)
        self.assertEqual(len(field_sigs), 1)

        field_sig = field_sigs[0]
        self.assertEqual(field_sig.field_name, 'char_field')
        self.assertIs(field_sig.field_type, models.CharField)

    def test_get_field_sig(self):
        """Testing ModelSignature.get_field_sig"""
        model_sig = ModelSignature(model_name='TestModel',
                                   table_name='testmodel')

        field_sig = FieldSignature.from_field(
            SignatureDefaultsModel._meta.get_field('char_field'))
        model_sig.add_field_sig(field_sig)

        self.assertIs(model_sig.get_field_sig('char_field'), field_sig)

    def test_get_field_sig_with_invalid_field_name(self):
        """Testing ModelSignature.get_field_sig with invalid field name"""
        model_sig = ModelSignature(model_name='TestModel',
                                   table_name='testmodel')

        self.assertIsNone(model_sig.get_field_sig('char_field'))

    def test_add_index(self):
        """Testing ModelSignature.add_index"""
        if Index is None:
            raise SkipTest('Meta.indexes is not supported on this version '
                           'of Django')

        model_sig = ModelSignature(model_name='TestModel',
                                   table_name='testmodel')
        model_sig.add_index(Index(name='index1', fields=['field1', 'field2']))

        index_sigs = list(model_sig.index_sigs)
        self.assertEqual(len(index_sigs), 1)

        index_sig = index_sigs[0]
        self.assertEqual(index_sig.name, 'index1')
        self.assertEqual(index_sig.fields, ['field1', 'field2'])

    def test_add_index_sig(self):
        """Testing ModelSignature.add_index_sig"""
        model_sig = ModelSignature(model_name='TestModel',
                                   table_name='testmodel')

        index_sig = IndexSignature(name='index1', fields=['field1', 'field2'])
        model_sig.add_index_sig(index_sig)

        self.assertEqual(list(model_sig.index_sigs), [index_sig])

    def test_has_unique_together_changed_and_old_applied(self):
        """Testing ModelSignature.has_unique_together_changed with equal
        unique_together contents and old unique_together applied
        """
        new_model_sig = ModelSignature(model_name='TestModel',
                                       table_name='testmodel',
                                       unique_together=[['field1', 'field2']])

        old_model_sig = ModelSignature(model_name='TestModel',
                                       table_name='testmodel',
                                       unique_together=(('field1', 'field2',)))
        old_model_sig._unique_together_applied = True

        self.assertFalse(
            new_model_sig.has_unique_together_changed(old_model_sig))

    def test_has_unique_together_changed_and_old_not_applied(self):
        """Testing ModelSignature.has_unique_together_changed with equal
        unique_together contents and old unique_together not applied
        """
        new_model_sig = ModelSignature(model_name='TestModel',
                                       table_name='testmodel',
                                       unique_together=[['field1', 'field2']])

        old_model_sig = ModelSignature(model_name='TestModel',
                                       table_name='testmodel',
                                       unique_together=(('field1', 'field2',)))
        old_model_sig._unique_together_applied = False

        self.assertTrue(
            new_model_sig.has_unique_together_changed(old_model_sig))

    def test_has_unique_together_changed_and_changed(self):
        """Testing ModelSignature.has_unique_together_changed with differences
        in unique_together
        """
        new_model_sig = ModelSignature(model_name='TestModel',
                                       table_name='testmodel',
                                       unique_together=[['field1', 'field3']])

        old_model_sig = ModelSignature(model_name='TestModel',
                                       table_name='testmodel',
                                       unique_together=(('field1', 'field2',)))
        old_model_sig._unique_together_applied = True

        self.assertTrue(
            new_model_sig.has_unique_together_changed(old_model_sig))

    def test_has_unique_together_changed_and_both_empty(self):
        """Testing ModelSignature.has_unique_together_changed with both empty
        """
        new_model_sig = ModelSignature(model_name='TestModel',
                                       table_name='testmodel',
                                       unique_together=[])

        old_model_sig = ModelSignature(model_name='TestModel',
                                       table_name='testmodel',
                                       unique_together=[])

        self.assertFalse(
            new_model_sig.has_unique_together_changed(old_model_sig))

    def test_clone(self):
        """Testing ModelSignature.clone"""
        model_sig = ModelSignature.from_model(SignatureFullModel)
        model_sig.add_index_sig(IndexSignature(name='index1',
                                               fields=['field1', 'field2']))
        cloned_model_sig = model_sig.clone()

        self.assertIsNot(cloned_model_sig, model_sig)
        self.assertEqual(cloned_model_sig, model_sig)

        for cloned_field_sig, field_sig in zip(cloned_model_sig.field_sigs,
                                               model_sig.field_sigs):
            self.assertIsNot(cloned_field_sig, field_sig)
            self.assertEqual(cloned_field_sig, field_sig)

        for cloned_index_sig, index_sig in zip(cloned_model_sig.index_sigs,
                                               model_sig.index_sigs):
            self.assertIsNot(cloned_index_sig, index_sig)
            self.assertEqual(cloned_index_sig, index_sig)

    def test_serialize_v1(self):
        """Testing ModelSignature.serialize (signature v1)"""
        model_sig = ModelSignature.from_model(SignatureFullModel)

        self.assertEqual(
            model_sig.serialize(sig_version=1),
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
                    'indexes': [],
                    'pk_column': 'id',
                    'unique_together': [],
                },
            })

    def test_serialize_v1_with_subclass(self):
        """Testing ModelSignature.serialize (signature v1) with subclass of
        model
        """
        model_sig = ModelSignature.from_model(SignatureChildModel)

        self.assertEqual(
            model_sig.serialize(sig_version=1),
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
                    'indexes': [],
                    'pk_column': 'signatureparentmodel_ptr_id',
                    'unique_together': [],
                },
            })


class IndexSignatureTests(BaseSignatureTestCase):
    """Unit tests for IndexSignature."""

    def test_from_index(self):
        """Testing IndexSignature.from_index"""
        if Index is None:
            raise SkipTest('Meta.indexes is not supported on this version '
                           'of Django')

        index_sig = IndexSignature.from_index(
            Index(name='index1', fields=['field1', 'field2']))

        self.assertEqual(index_sig.name, 'index1')
        self.assertEqual(index_sig.fields, ['field1', 'field2'])

    def test_deserialize_v1(self):
        """Testing IndexSignature.deserialize (signature v1)"""
        index_sig = IndexSignature.deserialize(
            {
                'name': 'index1',
                'fields': ['field1', 'field2'],
            },
            sig_version=1)

        self.assertEqual(index_sig.name, 'index1')
        self.assertEqual(index_sig.fields, ['field1', 'field2'])

    def test_clone(self):
        """Testing IndexSignature.clone"""
        index_sig = IndexSignature(name='index1', fields=['field1', 'field2'])
        cloned_index_sig = index_sig.clone()

        self.assertIsNot(cloned_index_sig, index_sig)
        self.assertEqual(cloned_index_sig, index_sig)
        self.assertIsNot(cloned_index_sig.fields, index_sig.fields)

    def test_serialize_v1(self):
        """Testing IndexSignature.serialize (signature v1)"""
        index_sig = IndexSignature(name='index1', fields=['field1', 'field2'])

        self.assertEqual(
            index_sig.serialize(sig_version=1),
            {
                'name': 'index1',
                'fields': ['field1', 'field2'],
            })

    def test_serialize_v1_without_name(self):
        """Testing IndexSignature.serialize (signature v1) without index name
        """
        index_sig = IndexSignature(fields=['field1', 'field2'])

        self.assertEqual(
            index_sig.serialize(sig_version=1),
            {
                'fields': ['field1', 'field2'],
            })

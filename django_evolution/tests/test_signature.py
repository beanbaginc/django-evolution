"""Unit tests for the signature-related functionality."""

from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.db.utils import DEFAULT_DB_ALIAS

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

from django_evolution.compat import six
from django_evolution.compat.apps import get_app
from django_evolution.compat.datastructures import OrderedDict
from django_evolution.compat.models import GenericForeignKey, GenericRelation
from django_evolution.consts import UpgradeMethod
from django_evolution.errors import MissingSignatureError
from django_evolution.models import Evolution
from django_evolution.signature import (AppSignature,
                                        ConstraintSignature,
                                        FieldSignature,
                                        IndexSignature,
                                        ModelSignature,
                                        ProjectSignature)
from django_evolution.support import supports_constraints, supports_indexes
from django_evolution.tests.base_test_case import EvolutionTestCase
from django_evolution.tests.decorators import (requires_meta_constraints,
                                               requires_meta_indexes)
from django_evolution.tests.models import BaseTestModel


class SignatureAnchor1(BaseTestModel):
    value = models.IntegerField()


class SignatureAnchor2(BaseTestModel):
    value = models.IntegerField()


class SignatureAnchor3(BaseTestModel):
    value = models.IntegerField()

    # Host a generic key here, too.
    content_type = models.ForeignKey(ContentType,
                                     on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey('content_type', 'object_id')


class SignatureFullModel(BaseTestModel):
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


class SignatureDefaultsModel(BaseTestModel):
    char_field = models.CharField(max_length=100)
    dec_field = models.DecimalField()
    m2m_field = models.ManyToManyField('self')
    fkey_field = models.ForeignKey(SignatureAnchor1,
                                   on_delete=models.CASCADE)


class SignatureParentModel(BaseTestModel):
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


class ConstraintSignatureTests(BaseSignatureTestCase):
    """Unit tests for ConstraintSignature."""

    @classmethod
    @requires_meta_constraints
    def setUpClass(cls):
        super(ConstraintSignatureTests, cls).setUpClass()

    def test_from_constraint(self):
        """Testing ConstraintSignature.from_constraint"""
        # We'll test against the built-in Django constraints, making sure we
        # handle all uses cases.
        constraint_sig = ConstraintSignature.from_constraint(
            UniqueConstraint(name='my_constraint',
                             fields=['field1', 'field2'],
                             condition=Q(field1__gte=100)))

        self.assertIs(constraint_sig.type, UniqueConstraint)
        self.assertEqual(constraint_sig.name, 'my_constraint')
        self.assertEqual(constraint_sig.attrs, {
            'fields': ('field1', 'field2'),
            'condition': Q(field1__gte=100),
        })

        constraint_sig = ConstraintSignature.from_constraint(
            CheckConstraint(name='my_constraint',
                            check=Q(field2__startswith='ABC')))

        self.assertIs(constraint_sig.type, CheckConstraint)
        self.assertEqual(constraint_sig.name, 'my_constraint')
        self.assertEqual(constraint_sig.attrs, {
            'check': Q(field2__startswith='ABC'),
        })

    def test_deserialize_v2(self):
        """Testing ConstraintSignature.deserialize (signature v2)"""
        constraint_sig = ConstraintSignature.deserialize(
            {
                'name': 'my_constraint',
                'type': 'django.db.models.UniqueConstraint',
                'attrs': {
                    'condition': {
                        '_deconstructed': True,
                        'args': (),
                        'kwargs': {
                            'field1__gte': 100,
                        },
                        'type': 'django.db.models.Q',
                    },
                    'fields': ['field1', 'field2'],
                },
            },
            sig_version=2)

        self.assertEqual(constraint_sig.name, 'my_constraint')
        self.assertEqual(constraint_sig.type, UniqueConstraint)
        self.assertEqual(constraint_sig.attrs, {
            'fields': ['field1', 'field2'],
            'condition': Q(field1__gte=100),
        })

    def test_clone(self):
        """Testing ConstraintSignature.clone"""
        constraint_sig = ConstraintSignature(
            name='constraint1',
            constraint_type=UniqueConstraint,
            attrs={
                'fields': ['field1', 'field2'],
                'condition': Q(field1=True),
            })
        cloned_constraint_sig = constraint_sig.clone()

        self.assertIsNot(cloned_constraint_sig, constraint_sig)
        self.assertEqual(cloned_constraint_sig, constraint_sig)
        self.assertIs(cloned_constraint_sig.type, constraint_sig.type)
        self.assertIsNot(cloned_constraint_sig.attrs, constraint_sig.attrs)
        self.assertIsNot(cloned_constraint_sig.attrs['fields'],
                         constraint_sig.attrs['fields'])
        self.assertIsNot(cloned_constraint_sig.attrs['condition'],
                         constraint_sig.attrs['condition'])

    def test_serialize_v2(self):
        """Testing ConstraintSignature.serialize (signature v2)"""
        constraint_sig = ConstraintSignature(
            name='my_constraint',
            constraint_type=UniqueConstraint,
            attrs={
                'fields': ['field1', 'field2'],
                'condition': Q(field1__gte=100),
            })

        self.assertEqual(
            constraint_sig.serialize(sig_version=2),
            {
                'name': 'my_constraint',
                'type': 'django.db.models.UniqueConstraint',
                'attrs': {
                    'condition': {
                        '_deconstructed': True,
                        'args': (),
                        'kwargs': {
                            'field1__gte': 100,
                        },
                        'type': 'django.db.models.Q',
                    },
                    'fields': ['field1', 'field2'],
                },
            })

    def test_eq(self):
        """Testing ConstraintSignature.__eq__"""
        self.assertEqual(
            ConstraintSignature(
                name='constraint1',
                constraint_type=UniqueConstraint,
                attrs={
                    'fields': ['field1', 'field2'],
                    'condition': Q(field1__gte=100),
                }),
            ConstraintSignature(
                name='constraint1',
                constraint_type=UniqueConstraint,
                attrs={
                    'fields': ['field1', 'field2'],
                    'condition': Q(field1__gte=100),
                }))

    def test_ne_with_different_names(self):
        """Testing ConstraintSignature.__ne__ with different names"""
        self.assertNotEqual(
            ConstraintSignature(
                name='constraint1',
                constraint_type=UniqueConstraint,
                attrs={
                    'fields': ['field1', 'field2'],
                    'condition': Q(field1__gte=100),
                }),
            ConstraintSignature(
                name='constraint2',
                constraint_type=UniqueConstraint,
                attrs={
                    'fields': ['field1', 'field2'],
                    'condition': Q(field1__gte=100),
                }))

    def test_ne_with_different_types(self):
        """Testing ConstraintSignature.__ne__ with different types"""
        self.assertNotEqual(
            ConstraintSignature(
                name='constraint1',
                constraint_type=UniqueConstraint,
                attrs={
                    'fields': ['field1', 'field2'],
                    'condition': Q(field1__gte=100),
                }),
            ConstraintSignature(
                name='constraint1',
                constraint_type=CheckConstraint,
                attrs={
                    'fields': ['field1', 'field2'],
                    'condition': Q(field1__gte=100),
                }))

    def test_ne_with_different_attrs(self):
        """Testing ConstraintSignature.__ne__ with different attrs"""
        self.assertNotEqual(
            ConstraintSignature(
                name='constraint1',
                constraint_type=UniqueConstraint,
                attrs={
                    'fields': ['field1', 'field2'],
                    'condition': Q(field1__gte=100),
                }),
            ConstraintSignature(
                name='constraint1',
                constraint_type=UniqueConstraint,
                attrs={
                    'fields': ['field1', 'field3'],
                    'condition': Q(field1__gte=100),
                }))

        self.assertNotEqual(
            ConstraintSignature(
                name='constraint1',
                constraint_type=UniqueConstraint,
                attrs={
                    'fields': ['field1', 'field2'],
                    'condition': Q(field1__gte=100),
                }),
            ConstraintSignature(
                name='constraint1',
                constraint_type=UniqueConstraint,
                attrs={
                    'fields': ['field1', 'field2'],
                    'condition': Q(field1=100),
                }))


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
            })

        self.assertEqual(
            set(
                app_sig.app_id
                for app_sig in project_sig.app_sigs
            ),
            set(['app1', 'app2']))

    def test_deserialize_v2(self):
        """Testing ProjectSignature.deserialize (signature v2)"""
        project_sig = ProjectSignature.deserialize(
            {
                '__version__': 2,
                'apps': {
                    'app1': {
                        'legacy_app_label': 'app1',
                        'models': {},
                    },
                    'app2': {
                        'legacy_app_label': 'app2',
                        'models': {},
                    },
                },
            })

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

    def test_get_app_sig(self):
        """Testing ProjectSignature.get_app_sig"""
        project_sig = ProjectSignature()

        app_sig = AppSignature.from_app(get_app('django_evolution'),
                                        database='default')
        project_sig.add_app_sig(app_sig)

        self.assertIs(project_sig.get_app_sig('django_evolution'), app_sig)

    def test_get_app_sig_with_no_result(self):
        """Testing ProjectSignature.get_app_sig with signature not found"""
        project_sig = ProjectSignature()

        self.assertIsNone(project_sig.get_app_sig('invalid'))

    def test_get_app_sig_with_no_result_and_required(self):
        """Testing ProjectSignature.get_app_sig with signature not found and
        required=True
        """
        project_sig = ProjectSignature()

        message = (
            'Unable to find an application signature for "invalid". '
            'syncdb/migrate might need to be run first.'
        )

        with self.assertRaisesMessage(MissingSignatureError, message):
            project_sig.get_app_sig('invalid', required=True)

    def test_remove_app_sig(self):
        """Testing ProjectSignature.remove_app_sig"""
        project_sig = ProjectSignature()

        app_sig = AppSignature.from_app(get_app('django_evolution'),
                                        database='default')
        project_sig.add_app_sig(app_sig)
        project_sig.remove_app_sig('django_evolution')

        self.assertIsNone(project_sig.get_app_sig('django_evolution'))

    def test_remove_app_sig_with_invalid_app_id(self):
        """Testing ProjectSignature.remove_app_sig with invalid app ID"""
        project_sig = ProjectSignature()

        message = (
            'An application signature for "invalid_app" could not be found.'
        )

        with self.assertRaisesMessage(MissingSignatureError, message):
            project_sig.remove_app_sig('invalid_app')

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

    def test_serialize_v2(self):
        """Testing ProjectSignature.serialize (signature v2)"""
        project_sig = ProjectSignature()
        project_sig.add_app_sig(AppSignature('test_app'))

        self.assertEqual(
            project_sig.serialize(sig_version=2),
            {
                '__version__': 2,
                'apps': {
                    'test_app': {
                        'legacy_app_label': 'test_app',
                        'models': {},
                    },
                },
            })

    def test_eq(self):
        """Testing ProjectSignature.__eq__"""
        project_sig1 = ProjectSignature()
        project_sig1.add_app_sig(AppSignature('app1'))
        project_sig1.add_app_sig(AppSignature('app2'))

        project_sig2 = ProjectSignature()
        project_sig2.add_app_sig(AppSignature('app2'))
        project_sig2.add_app_sig(AppSignature('app1'))

        self.assertEqual(project_sig1, project_sig2)

    def test_ne(self):
        """Testing ProjectSignature.__ne__"""
        project_sig1 = ProjectSignature()
        project_sig1.add_app_sig(AppSignature('app1'))
        project_sig1.add_app_sig(AppSignature('app2'))

        project_sig2 = ProjectSignature()
        project_sig2.add_app_sig(AppSignature('app1'))

        self.assertNotEqual(project_sig1, project_sig2)


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
        self.assertEqual(app_sig.upgrade_method, UpgradeMethod.EVOLUTIONS)
        self.assertIn('Version', model_names)
        self.assertIn('Evolution', model_names)

    def test_deserialize_v1(self):
        """Testing AppSignature.deserialize (signature v1)"""
        app_sig = AppSignature.deserialize(
            'evolutions_app',
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

        self.assertEqual(app_sig.app_id, 'evolutions_app')
        self.assertEqual(app_sig.upgrade_method, UpgradeMethod.EVOLUTIONS)

        model_sigs = sorted(app_sig.model_sigs,
                            key=lambda sig: sig.model_name)
        self.assertEqual(len(model_sigs), 2)

        model_sig = model_sigs[0]
        self.assertEqual(model_sig.model_name, 'model1')
        self.assertEqual(model_sig.table_name, 'app1_model1')

        model_sig = model_sigs[1]
        self.assertEqual(model_sig.model_name, 'model2')
        self.assertEqual(model_sig.table_name, 'app1_model2')

    def test_deserialize_v2(self):
        """Testing AppSignature.deserialize (signature v2)"""
        app_sig = AppSignature.deserialize(
            'app1',
            {
                'legacy_app_label': 'legacy',
                'models': {
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
            },
            sig_version=2)

        self.assertEqual(app_sig.app_id, 'app1')
        self.assertEqual(app_sig.legacy_app_label, 'legacy')
        self.assertIsNone(app_sig.upgrade_method)
        self.assertIsNone(app_sig.applied_migrations)

        model_sigs = sorted(app_sig.model_sigs,
                            key=lambda sig: sig.model_name)
        self.assertEqual(len(model_sigs), 2)

        model_sig = model_sigs[0]
        self.assertEqual(model_sig.model_name, 'model1')
        self.assertEqual(model_sig.table_name, 'app1_model1')

        model_sig = model_sigs[1]
        self.assertEqual(model_sig.model_name, 'model2')
        self.assertEqual(model_sig.table_name, 'app1_model2')

    def test_deserialize_v2_with_migrations(self):
        """Testing AppSignature.deserialize (signature v2) with
        upgrade_method=migrations
        """
        app_sig = AppSignature.deserialize(
            'app1',
            {
                'legacy_app_label': 'legacy',
                'upgrade_method': 'migrations',
                'applied_migrations': ['0001_initial', '0002_last_applied'],
                'models': {},
            },
            sig_version=2)

        self.assertEqual(app_sig.app_id, 'app1')
        self.assertEqual(app_sig.legacy_app_label, 'legacy')
        self.assertEqual(app_sig.upgrade_method, UpgradeMethod.MIGRATIONS)
        self.assertIsInstance(app_sig.applied_migrations, set)
        self.assertEqual(app_sig.applied_migrations,
                         set(['0001_initial', '0002_last_applied']))

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

    def test_get_model_sig_with_no_result(self):
        """Testing AppSignature.get_model_sig with signature not found"""
        app_sig = AppSignature('django_evolution')

        self.assertIsNone(app_sig.get_model_sig('invalid'))

    def test_get_model_sig_with_no_result_and_required(self):
        """Testing AppSignature.get_model_sig with signature not found and
        required=True
        """
        app_sig = AppSignature('django_evolution')

        message = (
            'Unable to find a model signature for "django_evolution.Invalid". '
            'syncdb/migrate might need to be run first.'
        )

        with self.assertRaisesMessage(MissingSignatureError, message):
            app_sig.get_model_sig('Invalid', required=True)

    def test_remove_model_sig(self):
        """Testing AppSignature.remove_model_sig"""
        app_sig = AppSignature('django_evolution')

        model_sig = ModelSignature.from_model(Evolution)
        app_sig.add_model_sig(model_sig)
        app_sig.remove_model_sig('Evolution')

        self.assertIsNone(app_sig.get_model_sig('Evolution'))

    def test_remove_model_sig_with_invalid_model_name(self):
        """Testing AppSignature.remove_model_sig with invalid model name"""
        app_sig = AppSignature('django_evolution')

        message = 'A model signature for "Evolution" could not be found.'

        with self.assertRaisesMessage(MissingSignatureError, message):
            app_sig.remove_model_sig('Evolution')

    def test_clone(self):
        """Testing AppSignature.clone"""
        app_sig = AppSignature.from_app(get_app('django_evolution'),
                                        database=DEFAULT_DB_ALIAS)
        app_sig.legacy_app_label = 'legacy'
        app_sig.upgrade_method = UpgradeMethod.MIGRATIONS
        app_sig.applied_migrations = set(['0001_initial', '0002_last_applied'])

        cloned_app_sig = app_sig.clone()
        self.assertEqual(cloned_app_sig.app_id, 'django_evolution')
        self.assertEqual(cloned_app_sig.legacy_app_label, 'legacy')
        self.assertEqual(cloned_app_sig.upgrade_method,
                         UpgradeMethod.MIGRATIONS)
        self.assertEqual(cloned_app_sig.applied_migrations,
                         set(['0001_initial', '0002_last_applied']))

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
                        'constraints': [],
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

    def test_serialize_v2(self):
        """Testing AppSignature.serialize (signature v2)"""
        app_sig = AppSignature('testapp',
                               upgrade_method=UpgradeMethod.EVOLUTIONS)
        app_sig.add_model_sig(ModelSignature(model_name='MyModel',
                                             table_name='testapp_mymodel'))

        self.assertEqual(
            app_sig.serialize(sig_version=2),
            {
                'legacy_app_label': 'testapp',
                'upgrade_method': 'evolutions',
                'models': {
                    'MyModel': {
                        'fields': {},
                        'meta': {
                            'constraints': [],
                            'db_table': 'testapp_mymodel',
                            'db_tablespace': None,
                            'indexes': [],
                            'index_together': [],
                            'unique_together': [],
                            'pk_column': None,
                            '__unique_together_applied': False,
                        },
                    },
                },
            })

    def test_serialize_v2_with_migrations(self):
        """Testing AppSignature.serialize (signature v2) with migrations
        information
        """
        app_sig = AppSignature('testapp',
                               upgrade_method=UpgradeMethod.MIGRATIONS,
                               applied_migrations=['0002_last_applied',
                                                   '0001_initial'])
        app_sig.add_model_sig(ModelSignature(model_name='MyModel',
                                             table_name='testapp_mymodel'))

        self.assertEqual(
            app_sig.serialize(sig_version=2),
            {
                'legacy_app_label': 'testapp',
                'upgrade_method': 'migrations',
                'applied_migrations': ['0001_initial', '0002_last_applied'],
                'models': {
                    'MyModel': {
                        'fields': {},
                        'meta': {
                            'constraints': [],
                            'db_table': 'testapp_mymodel',
                            'db_tablespace': None,
                            'indexes': [],
                            'index_together': [],
                            'unique_together': [],
                            'pk_column': None,
                            '__unique_together_applied': False,
                        },
                    },
                },
            })

    def test_serialize_v2_with_router(self):
        """Testing AppSignature.serialize (signature v2) with
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

        app_sig_dict = app_sig.serialize(sig_version=2)
        self.assertIn('models', app_sig_dict)

        models_sig_dict = app_sig_dict['models']
        self.assertIn('Evolution', models_sig_dict)
        self.assertNotIn('Version', models_sig_dict)

    def test_diff_with_app_id(self):
        """Testing AppSignature.diff with app_id"""
        old_app_sig = AppSignature('app1', legacy_app_label='legacy')
        new_app_sig = AppSignature('app2', legacy_app_label='legacy')

        self.assertEqual(
            new_app_sig.diff(old_app_sig),
            {
                'meta_changed': {
                    'app_id': {
                        'old': 'app1',
                        'new': 'app2',
                    },
                },
            })

    def test_diff_with_legacy_app_label(self):
        """Testing AppSignature.diff with legacy_app_label"""
        old_app_sig = AppSignature('app', legacy_app_label='legacy1')
        new_app_sig = AppSignature('app', legacy_app_label='legacy2')

        self.assertEqual(
            new_app_sig.diff(old_app_sig),
            {
                'meta_changed': {
                    'legacy_app_label': {
                        'old': 'legacy1',
                        'new': 'legacy2',
                    },
                },
            })

    def test_diff_with_upgrade_method_evo_to_migrations(self):
        """Testing AppSignature.diff with upgrade_method changing from
        evolutions to migrations
        """
        old_app_sig = AppSignature('testapp',
                                   upgrade_method=UpgradeMethod.EVOLUTIONS)
        new_app_sig = AppSignature('testapp',
                                   upgrade_method=UpgradeMethod.MIGRATIONS)

        self.assertEqual(
            new_app_sig.diff(old_app_sig),
            {
                'meta_changed': {
                    'upgrade_method': {
                        'old': 'evolutions',
                        'new': 'migrations',
                    },
                },
            })

    def test_diff_with_upgrade_method_none_to_migrations(self):
        """Testing AppSignature.diff with upgrade_method changing from
        None to migrations
        """
        old_app_sig = AppSignature('testapp',
                                   upgrade_method=None)
        new_app_sig = AppSignature('testapp',
                                   upgrade_method=UpgradeMethod.MIGRATIONS)

        self.assertEqual(new_app_sig.diff(old_app_sig), {})

    def test_diff_with_upgrade_method_sig_v1_none_to_migrations(self):
        """Testing AppSignature.diff with upgrade_method loaded from signature
        v1, changing from None to migrations
        """
        old_app_sig = AppSignature('testapp',
                                   upgrade_method=None)
        old_app_sig._loaded_sig_version = 1

        new_app_sig = AppSignature('testapp',
                                   upgrade_method=UpgradeMethod.MIGRATIONS)

        self.assertEqual(new_app_sig.diff(old_app_sig), {})

        # Now add a model signature.
        model_sig = ModelSignature(model_name='MyModel1',
                                   table_name='testapp_mymodel1')
        old_app_sig.add_model_sig(model_sig)

        self.assertEqual(
            new_app_sig.diff(old_app_sig),
            {
                'meta_changed': {
                    'upgrade_method': {
                        'old': None,
                        'new': 'migrations',
                    },
                },
            })

    def test_eq(self):
        """Testing AppSignature.__eq__"""
        app_sig1 = AppSignature('app',
                                legacy_app_label='legacy',
                                upgrade_method=UpgradeMethod.MIGRATIONS,
                                applied_migrations=['0001_initial',
                                                    '0002_last_applied'])
        app_sig1.add_model_sig(ModelSignature(model_name='MyModel1',
                                              table_name='testapp_mymodel1'))
        app_sig1.add_model_sig(ModelSignature(model_name='MyModel2',
                                              table_name='testapp_mymodel2'))

        app_sig2 = AppSignature('app',
                                legacy_app_label='legacy',
                                upgrade_method=UpgradeMethod.MIGRATIONS,
                                applied_migrations=['0002_last_applied',
                                                    '0001_initial'])
        app_sig2.add_model_sig(ModelSignature(model_name='MyModel2',
                                              table_name='testapp_mymodel2'))
        app_sig2.add_model_sig(ModelSignature(model_name='MyModel1',
                                              table_name='testapp_mymodel1'))

        self.assertEqual(app_sig1, app_sig2)

    def test_ne_with_different_app_ids(self):
        """Testing AppSignature.__ne__ with different app IDs"""
        self.assertNotEqual(AppSignature('app1'),
                            AppSignature('app2'))

    def test_ne_with_different_legacy_app_labels(self):
        """Testing AppSignature.__ne__ with different legacy_app_label values
        """
        app_sig1 = AppSignature('app1',
                                legacy_app_label='legacy1')
        app_sig2 = AppSignature('app1',
                                legacy_app_label='legacy2')

        self.assertNotEqual(app_sig1, app_sig2)

    def test_ne_with_different_model_sigs(self):
        """Testing AppSignature.__ne__ with different model sigs"""
        app_sig1 = AppSignature('app')
        app_sig1.add_model_sig(ModelSignature(model_name='MyModel1',
                                              table_name='testapp_mymodel1'))
        app_sig1.add_model_sig(ModelSignature(model_name='MyModel2',
                                              table_name='testapp_mymodel2'))

        app_sig2 = AppSignature('app')
        app_sig2.add_model_sig(ModelSignature(model_name='MyModel2',
                                              table_name='testapp_mymodel2'))
        app_sig2.add_model_sig(ModelSignature(model_name='MyModel1',
                                              table_name='testapp_mymodel1'))

        self.assertEqual(app_sig1, app_sig2)

    def test_ne_with_different_upgrade_method(self):
        """Testing AppSignature.__ne__ with different upgrade_method values"""
        app_sig1 = AppSignature('app1',
                                upgrade_method=UpgradeMethod.EVOLUTIONS)
        app_sig2 = AppSignature('app1',
                                upgrade_method=UpgradeMethod.MIGRATIONS)

        self.assertNotEqual(app_sig1, app_sig2)

    def test_ne_with_different_applied_migrations(self):
        """Testing AppSignature.__ne__ with different applied_migrations"""
        app_sig1 = AppSignature('app1',
                                upgrade_method=UpgradeMethod.MIGRATIONS,
                                applied_migrations=['0001_initial'])
        app_sig2 = AppSignature('app1',
                                upgrade_method=UpgradeMethod.MIGRATIONS,
                                applied_migrations=['0001_initial',
                                                    '0002_last_applied'])

        self.assertNotEqual(app_sig1, app_sig2)


class FieldSignatureTests(BaseSignatureTestCase):
    """Unit tests for FieldSignature."""

    def test_from_field(self):
        """Testing FieldSignature.from_field"""
        field_sig = FieldSignature.from_field(
            SignatureFullModel._meta.get_field('ref3'))

        self.assertEqual(field_sig.field_name, 'ref3')
        self.assertIs(field_sig.field_type, models.ForeignKey)
        self.assertEqual(field_sig.related_model, 'tests.Anchor2')
        self.assertEqual(
            field_sig.field_attrs,
            {
                'db_column': 'value',
            })

    def test_deserialize_v1(self):
        """Testing FieldSignature.deserialize (signature v1)"""
        field_sig = FieldSignature.deserialize(
            'myfield',
            {
                'field_type': models.ForeignKey,
                'null': False,
                'db_column': 'test_column',
                'related_model': 'tests.Anchor2',
            },
            sig_version=1)

        self.assertEqual(field_sig.field_name, 'myfield')
        self.assertIs(field_sig.field_type, models.ForeignKey)
        self.assertEqual(field_sig.related_model, 'tests.Anchor2')
        self.assertEqual(
            field_sig.field_attrs,
            {
                'null': False,
                'db_column': 'test_column',
            })

    def test_deserialize_v2(self):
        """Testing FieldSignature.deserialize (signature v2)"""
        field_sig = FieldSignature.deserialize(
            'myfield',
            {
                'type': 'django.db.models.ForeignKey',
                'related_model': 'tests.Anchor2',
                'attrs': {
                    'null': False,
                    'db_column': 'test_column',
                },
            },
            sig_version=2)

        self.assertEqual(field_sig.field_name, 'myfield')
        self.assertIs(field_sig.field_type, models.ForeignKey)
        self.assertEqual(field_sig.related_model, 'tests.Anchor2')
        self.assertEqual(
            field_sig.field_attrs,
            {
                'null': False,
                'db_column': 'test_column',
            })

    def test_deserialize_v2_with_legacy_django_fields_module(self):
        """Testing FieldSignature.deserialize (signature v2) with legacy
        django.db.models.fields module
        """
        field_sig = FieldSignature.deserialize(
            'myfield',
            {
                'type': 'django.db.models.fields.ForeignKey',
                'related_model': 'tests.Anchor2',
                'attrs': {
                    'null': False,
                    'db_column': 'test_column',
                },
            },
            sig_version=2)

        self.assertEqual(field_sig.field_name, 'myfield')
        self.assertIs(field_sig.field_type, models.ForeignKey)
        self.assertEqual(field_sig.related_model, 'tests.Anchor2')
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
            SignatureFullModel._meta.get_field('ref1'))

        cloned_field_sig = field_sig.clone()
        self.assertIsNot(cloned_field_sig, field_sig)
        self.assertEqual(cloned_field_sig, field_sig)
        self.assertIsNot(cloned_field_sig.field_attrs, field_sig.field_attrs)
        self.assertEqual(cloned_field_sig.related_model,
                         field_sig.related_model)

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
                'max_length': 100,
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

    def test_serialize_v2(self):
        """Testing FieldSignature.serialize (signature v2)"""
        field_sig = FieldSignature.from_field(
            SignatureFullModel._meta.get_field('null_field'))

        self.assertEqual(
            field_sig.serialize(sig_version=2),
            {
                'type': 'django.db.models.IntegerField',
                'attrs': {
                    'db_column': 'size_column',
                    'null': True,
                },
            })

    def test_serialize_v2_with_unique(self):
        """Testing FieldSignature.serialize (signature v2) with _unique
        stored as unique
        """
        field_sig = FieldSignature.from_field(
            SignatureFullModel._meta.get_field('id_card'))

        self.assertEqual(
            field_sig.serialize(sig_version=2),
            {
                'type': 'django.db.models.IntegerField',
                'attrs': {
                    'db_index': True,
                    'unique': True,
                },
            })

    def test_serialize_v2_with_defaults_not_stored(self):
        """Testing FieldSignature.serialize (signature v2) with field
        defaults not stored
        """
        meta = SignatureDefaultsModel._meta

        field_sig = FieldSignature.from_field(meta.get_field('char_field'))
        self.assertEqual(
            field_sig.serialize(sig_version=2),
            {
                'type': 'django.db.models.CharField',
                'attrs': {
                    'max_length': 100,
                },
            })

        field_sig = FieldSignature.from_field(meta.get_field('dec_field'))
        self.assertEqual(
            field_sig.serialize(sig_version=2),
            {
                'type': 'django.db.models.DecimalField',
            })

        field_sig = FieldSignature.from_field(meta.get_field('m2m_field'))
        self.assertEqual(
            field_sig.serialize(sig_version=2),
            {
                'type': 'django.db.models.ManyToManyField',
                'related_model': 'tests.DefaultsModel',
            })

        field_sig = FieldSignature.from_field(meta.get_field('fkey_field'))
        self.assertEqual(
            field_sig.serialize(sig_version=2),
            {
                'type': 'django.db.models.ForeignKey',
                'related_model': 'tests.Anchor1',
            })

    def test_eq(self):
        """Testing FieldSignature.__eq__"""
        field_sig1 = FieldSignature(
            field_name='field1',
            field_type=models.ForeignKey,
            field_attrs=OrderedDict([
                ('db_index', True),
                ('null', True),
            ]),
            related_model='tests.Anchor1')

        field_sig2 = FieldSignature(
            field_name='field1',
            field_type=models.ForeignKey,
            field_attrs=OrderedDict([
                ('null', True),
                ('db_index', True),
            ]),
            related_model='tests.Anchor1')

        self.assertEqual(field_sig1, field_sig2)

    def test_ne_with_different_name(self):
        """Testing FieldSignature.__ne__ with different field_name"""
        field_sig1 = FieldSignature(
            field_name='field1',
            field_type=models.ForeignKey,
            field_attrs=OrderedDict([
                ('db_index', True),
                ('null', True),
            ]),
            related_model='tests.Anchor1')

        field_sig2 = FieldSignature(
            field_name='field2',
            field_type=models.ForeignKey,
            field_attrs=OrderedDict([
                ('null', True),
                ('db_index', True),
            ]),
            related_model='tests.Anchor1')

        self.assertNotEqual(field_sig1, field_sig2)

    def test_ne_with_different_type(self):
        """Testing FieldSignature.__ne__ with different field_type"""
        field_sig1 = FieldSignature(
            field_name='field1',
            field_type=models.ForeignKey,
            field_attrs=OrderedDict([
                ('db_index', True),
                ('null', True),
            ]),
            related_model='tests.Anchor1')

        field_sig2 = FieldSignature(
            field_name='field1',
            field_type=models.CharField,
            field_attrs=OrderedDict([
                ('null', True),
                ('db_index', True),
            ]),
            related_model='tests.Anchor1')

        self.assertNotEqual(field_sig1, field_sig2)

    def test_ne_with_different_attrs(self):
        """Testing FieldSignature.__ne__ with different field_attrs"""
        field_sig1 = FieldSignature(
            field_name='field1',
            field_type=models.ForeignKey,
            field_attrs=OrderedDict([
                ('db_index', True),
                ('null', True),
            ]),
            related_model='tests.Anchor1')

        field_sig2 = FieldSignature(
            field_name='field1',
            field_type=models.ForeignKey,
            field_attrs=OrderedDict([
                ('db_index', True),
            ]),
            related_model='tests.Anchor1')

        self.assertNotEqual(field_sig1, field_sig2)

    def test_ne_with_different_related_model(self):
        """Testing FieldSignature.__ne__ with different related_model"""
        field_sig1 = FieldSignature(
            field_name='field1',
            field_type=models.ForeignKey,
            field_attrs=OrderedDict([
                ('db_index', True),
                ('null', True),
            ]),
            related_model='tests.Anchor1')

        field_sig2 = FieldSignature(
            field_name='field1',
            field_type=models.ForeignKey,
            field_attrs=OrderedDict([
                ('db_index', True),
                ('null', True),
            ]),
            related_model='tests.Anchor2')

        self.assertNotEqual(field_sig1, field_sig2)


class ModelSignatureTests(BaseSignatureTestCase):
    """Unit tests for ModelSignature."""

    def test_from_model(self):
        """Testing ModelSignature.from_model"""
        class ModelSignatureFromModelTestModel(BaseTestModel):
            field1 = models.CharField(max_length=100)
            field2 = models.IntegerField(null=True)
            field3 = models.BooleanField()

            class Meta(BaseTestModel.Meta):
                db_table = 'my_table'
                db_tablespace = 'my_tablespace'
                index_together = (('field1', 'field2'),)
                unique_together = (('field2', 'field3'),)

                if supports_constraints:
                    constraints = [
                        UniqueConstraint(fields=['field1', 'field3'],
                                         name='my_unique_constraint',
                                         condition=Q(field3=True)),
                        CheckConstraint(name='my_check_constraint',
                                        check=Q(field2__gte=42)),
                    ]

                if supports_indexes:
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

        if supports_constraints:
            constraint_sigs = list(model_sig.constraint_sigs)
            self.assertEqual(len(constraint_sigs), 2)

            constraint_sig = constraint_sigs[0]
            self.assertIs(constraint_sig.type, UniqueConstraint)
            self.assertEqual(constraint_sig.name, 'my_unique_constraint')
            self.assertEqual(constraint_sig.attrs, {
                'fields': ('field1', 'field3'),
                'condition': Q(field3=True),
            })

            constraint_sig = constraint_sigs[1]
            self.assertIs(constraint_sig.type, CheckConstraint)
            self.assertEqual(constraint_sig.name, 'my_check_constraint')
            self.assertEqual(constraint_sig.attrs, {
                'check': Q(field2__gte=42),
            })

        if supports_indexes:
            index_sigs = list(model_sig.index_sigs)
            self.assertEqual(len(index_sigs), 2)

            index_sig = index_sigs[0]
            self.assertEqual(index_sig.name, 'index1')
            self.assertEqual(index_sig.fields, ['field1'])

            index_sig = index_sigs[1]
            self.assertEqual(index_sig.name, 'index2')
            self.assertEqual(index_sig.fields, ['field3'])

    def test_deserialize_v1(self):
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

    def test_deserialize_v2(self):
        """Testing ModelSignature.deserialize (signature v2)"""
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
                        'type': 'django.db.models.CharField',
                        'attrs': {
                            'max_length': 100,
                        },
                    },
                },
            },
            sig_version=2)

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

    def test_get_field_sig_with_no_result(self):
        """Testing ModelSignature.get_field_sig with signature not found"""
        model_sig = ModelSignature(model_name='TestModel',
                                   table_name='testmodel')

        self.assertIsNone(model_sig.get_field_sig('invalid'))

    def test_get_field_sig_with_no_result_and_required(self):
        """Testing AppSignature.get_field_sig with signature not found and
        required=True
        """
        model_sig = ModelSignature(model_name='TestModel',
                                   table_name='testmodel')

        message = (
            'Unable to find a field signature for "TestModel.invalid". '
            'syncdb/migrate might need to be run first.'
        )

        with self.assertRaisesMessage(MissingSignatureError, message):
            model_sig.get_field_sig('invalid', required=True)

    def test_remove_field_sig(self):
        """Testing ModelSignature.remove_field_sig"""
        model_sig = ModelSignature(model_name='TestModel',
                                   table_name='testmodel')

        field_sig = FieldSignature.from_field(
            SignatureDefaultsModel._meta.get_field('char_field'))
        model_sig.add_field_sig(field_sig)
        model_sig.remove_field_sig('char_field')

        self.assertIsNone(model_sig.get_field_sig('char_field'))

    def test_remove_field_sig_with_invalid_field_name(self):
        """Testing ModelSignature.remove_field_sig with invalid field name"""
        model_sig = ModelSignature(model_name='TestModel',
                                   table_name='testmodel')

        message = 'A field signature for "char_field" could not be found.'

        with self.assertRaisesMessage(MissingSignatureError, message):
            model_sig.remove_field_sig('char_field')

    @requires_meta_constraints
    def test_add_constraint(self):
        """Testing ModelSignature.add_constraint"""
        model_sig = ModelSignature(model_name='TestModel',
                                   table_name='testmodel')
        model_sig.add_constraint(UniqueConstraint(
            name='my_constraint',
            fields=['field1', 'field2'],
            condition=Q(field1__gte=100)))

        constraint_sigs = list(model_sig.constraint_sigs)
        self.assertEqual(len(constraint_sigs), 1)

        constraint_sig = constraint_sigs[0]
        self.assertIs(constraint_sig.type, UniqueConstraint)
        self.assertEqual(constraint_sig.name, 'my_constraint')
        self.assertEqual(constraint_sig.attrs, {
            'fields': ('field1', 'field2'),
            'condition': Q(field1__gte=100),
        })

    @requires_meta_constraints
    def test_add_constraint_sig(self):
        """Testing ModelSignature.add_constraint_sig"""
        model_sig = ModelSignature(model_name='TestModel',
                                   table_name='testmodel')

        constraint_sig = ConstraintSignature(
            name='my_constraint',
            constraint_type=UniqueConstraint,
            attrs={
                'fields': ('field1', 'field2'),
                'condition': Q(field1__gte=100),
            })
        model_sig.add_constraint_sig(constraint_sig)

        self.assertEqual(list(model_sig.constraint_sigs), [constraint_sig])

    @requires_meta_indexes
    def test_add_index(self):
        """Testing ModelSignature.add_index"""
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
        if supports_constraints:
            model_sig.add_constraint_sig(ConstraintSignature(
                name='constraint1',
                constraint_type=UniqueConstraint,
                attrs={
                    'fields': ['field1', 'field2'],
                }))

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

        if supports_constraints:
            for (cloned_constraint_sig,
                 constraint_sig) in zip(cloned_model_sig.constraint_sigs,
                                        model_sig.constraint_sigs):
                self.assertIsNot(cloned_constraint_sig, constraint_sig)
                self.assertEqual(cloned_constraint_sig, constraint_sig)

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
                    'constraints': [],
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
                    'constraints': [],
                    'db_table': 'tests_childmodel',
                    'db_tablespace': '',
                    'index_together': [],
                    'indexes': [],
                    'pk_column': 'signatureparentmodel_ptr_id',
                    'unique_together': [],
                },
            })

    def test_serialize_v2(self):
        """Testing ModelSignature.serialize (signature v2)"""
        model_sig = ModelSignature.from_model(SignatureFullModel)

        self.assertEqual(
            model_sig.serialize(sig_version=2),
            {
                'fields': {
                    'char_field': {
                        'type': 'django.db.models.CharField',
                        'attrs': {
                            'max_length': 20,
                        },
                    },
                    'content_type': {
                        'type': 'django.db.models.ForeignKey',
                        'related_model': 'contenttypes.ContentType',
                    },
                    'dec_field': {
                        'type': 'django.db.models.DecimalField',
                        'attrs': {
                            'decimal_places': 4,
                            'max_digits': 10,
                        },
                    },
                    'id': {
                        'type': 'django.db.models.AutoField',
                        'attrs': {
                            'primary_key': True,
                        },
                    },
                    'id_card': {
                        'type': 'django.db.models.IntegerField',
                        'attrs': {
                            'db_index': True,
                            'unique': True,
                        }
                    },
                    'int_field': {
                        'type': 'django.db.models.IntegerField',
                    },
                    'null_field': {
                        'type': 'django.db.models.IntegerField',
                        'attrs': {
                            'db_column': 'size_column',
                            'null': True,
                        }
                    },
                    'object_id': {
                        'type': 'django.db.models.PositiveIntegerField',
                        'attrs': {
                            'db_index': True,
                        },
                    },
                    'ref1': {
                        'type': 'django.db.models.ForeignKey',
                        'related_model': 'tests.Anchor1',
                    },
                    'ref2': {
                        'type': 'django.db.models.ForeignKey',
                        'related_model': 'tests.Anchor1',
                    },
                    'ref3': {
                        'type': 'django.db.models.ForeignKey',
                        'related_model': 'tests.Anchor2',
                        'attrs': {
                            'db_column': 'value',
                        },
                    },
                    'ref4': {
                        'type': 'django.db.models.ForeignKey',
                        'related_model': 'tests.TestModel',
                    },
                    'ref5': {
                        'type': 'django.db.models.ManyToManyField',
                        'related_model': 'tests.Anchor3',
                    },
                    'ref6': {
                        'type': 'django.db.models.ManyToManyField',
                        'related_model': 'tests.Anchor3',
                    },
                    'ref7': {
                        'type': 'django.db.models.ManyToManyField',
                        'related_model': 'tests.TestModel',
                    },
                },
                'meta': {
                    '__unique_together_applied': True,
                    'constraints': [],
                    'db_table': 'tests_testmodel',
                    'db_tablespace': '',
                    'index_together': [],
                    'indexes': [],
                    'pk_column': 'id',
                    'unique_together': [],
                },
            })

    def test_serialize_v2_with_subclass(self):
        """Testing ModelSignature.serialize (signature v2) with subclass of
        model
        """
        model_sig = ModelSignature.from_model(SignatureChildModel)

        self.assertEqual(
            model_sig.serialize(sig_version=2),
            {
                'fields': {
                    'child_field': {
                        'type': 'django.db.models.CharField',
                        'attrs': {
                            'max_length': 20,
                        },
                    },
                    'signatureparentmodel_ptr': {
                        'type': 'django.db.models.OneToOneField',
                        'related_model': 'tests.ParentModel',
                        'attrs': {
                            'primary_key': True,
                            'unique': True,
                        },
                    },
                },
                'meta': {
                    '__unique_together_applied': True,
                    'constraints': [],
                    'db_table': 'tests_childmodel',
                    'db_tablespace': '',
                    'index_together': [],
                    'indexes': [],
                    'pk_column': 'signatureparentmodel_ptr_id',
                    'unique_together': [],
                },
            })

    def test_eq(self):
        """Testing ModelSignature.__eq__"""
        self.assertEqual(ModelSignature(model_name='TestModel',
                                        table_name='testmodel'),
                         ModelSignature(model_name='TestModel',
                                        table_name='testmodel'))

        model_sig1 = ModelSignature(
            model_name='TestModel1',
            table_name='testmodel1',
            db_tablespace='tablespace',
            pk_column='id',
            index_together=[
                ('field1', 'field2'),
            ],
            unique_together=[
                ('field3', 'field4'),
            ])
        model_sig1._unique_together_applied = True
        model_sig1.add_field_sig(FieldSignature.from_field(
            SignatureDefaultsModel._meta.get_field('char_field')))
        model_sig1.add_field_sig(FieldSignature.from_field(
            SignatureDefaultsModel._meta.get_field('dec_field')))
        model_sig1.add_index_sig(IndexSignature(
            name='index1',
            fields=['field5', 'field6']))
        model_sig1.add_index_sig(IndexSignature(
            fields=['field7', 'field8']))

        model_sig2 = ModelSignature(
            model_name='TestModel1',
            table_name='testmodel1',
            db_tablespace='tablespace',
            pk_column='id',
            index_together=[
                ['field1', 'field2'],
            ],
            unique_together=[
                ['field3', 'field4'],
            ])
        model_sig2._unique_together_applied = True
        model_sig2.add_field_sig(FieldSignature.from_field(
            SignatureDefaultsModel._meta.get_field('dec_field')))
        model_sig2.add_field_sig(FieldSignature.from_field(
            SignatureDefaultsModel._meta.get_field('char_field')))
        model_sig2.add_index_sig(IndexSignature(
            fields=['field7', 'field8']))
        model_sig2.add_index_sig(IndexSignature(
            name='index1',
            fields=['field5', 'field6']))

        if supports_constraints:
            model_sig1.add_index_sig(ConstraintSignature(
                name='my_constraint',
                constraint_type=UniqueConstraint,
                attrs={
                    'fields': ['field1', 'field2'],
                    'condition': Q(field1=True),
                }))
            model_sig2.add_index_sig(ConstraintSignature(
                name='my_constraint',
                constraint_type=UniqueConstraint,
                attrs={
                    'fields': ['field1', 'field2'],
                    'condition': Q(field1=True),
                }))

        self.assertEqual(model_sig1, model_sig2)

    def test_ne_with_different_model_name(self):
        """Testing ModelSignature.__ne__ with different model_name"""
        self.assertNotEqual(ModelSignature(model_name='TestModel1',
                                           table_name='testmodel'),
                            ModelSignature(model_name='TestModel2',
                                           table_name='testmodel'))

    def test_ne_with_different_table_name(self):
        """Testing ModelSignature.__ne__ with different table_name"""
        self.assertNotEqual(ModelSignature(model_name='TestModel',
                                           table_name='testmodel1'),
                            ModelSignature(model_name='TestModel',
                                           table_name='testmodel2'))

    def test_ne_with_different_tablespace(self):
        """Testing ModelSignature.__ne__ with different db_tablespace"""
        self.assertNotEqual(ModelSignature(model_name='TestModel',
                                           table_name='testmodel',
                                           db_tablespace='space1'),
                            ModelSignature(model_name='TestModel',
                                           table_name='testmodel',
                                           db_tablespace='space2'))

    @requires_meta_constraints
    def test_ne_with_different_constraint_sigs(self):
        """Testing ModelSignature.__ne__ with different constraint signatures
        """
        model_sig1 = ModelSignature(model_name='TestModel',
                                    table_name='testmodel')
        model_sig1.add_constraint_sig(ConstraintSignature(
            name='constraint1',
            constraint_type=UniqueConstraint,
            attrs={
                'fields': ['field1', 'field2'],
            }))

        model_sig2 = ModelSignature(model_name='TestModel',
                                    table_name='testmodel')
        model_sig1.add_constraint_sig(ConstraintSignature(
            name='constraint1',
            constraint_type=UniqueConstraint,
            attrs={
                'fields': ['field1', 'field2'],
                'condition': Q(field1=True),
            }))

        self.assertNotEqual(model_sig1, model_sig2)

    def test_ne_with_different_index_sigs(self):
        """Testing ModelSignature.__ne__ with different index signatures"""
        model_sig1 = ModelSignature(model_name='TestModel',
                                    table_name='testmodel')
        model_sig1.add_index_sig(IndexSignature(fields=['field1']))

        model_sig2 = ModelSignature(model_name='TestModel',
                                    table_name='testmodel')
        model_sig2.add_index_sig(IndexSignature(fields=['field2']))

        self.assertNotEqual(model_sig1, model_sig2)

    def test_ne_with_different_index_together(self):
        """Testing ModelSignature.__ne__ with different index_together"""
        model_sig1 = ModelSignature(
            model_name='TestModel',
            table_name='testmodel',
            index_together=[
                ('field1', 'field2'),
            ])

        model_sig2 = ModelSignature(
            model_name='TestModel',
            table_name='testmodel',
            index_together=[
                ('field1', 'field2'),
                ('field3', 'field4'),
            ])

        self.assertNotEqual(model_sig1, model_sig2)

    def test_ne_with_different_unique_together(self):
        """Testing ModelSignature.__ne__ with different unique_together"""
        model_sig1 = ModelSignature(
            model_name='TestModel',
            table_name='testmodel',
            unique_together=[
                ('field1', 'field2'),
            ])

        model_sig2 = ModelSignature(
            model_name='TestModel',
            table_name='testmodel',
            unique_together=[
                ('field1', 'field2'),
                ('field3', 'field4'),
            ])

        self.assertNotEqual(model_sig1, model_sig2)

    def test_ne_with_different_pk_column(self):
        """Testing ModelSignature.__ne__ with different pk_column"""
        self.assertNotEqual(ModelSignature(model_name='TestModel',
                                           table_name='testmodel',
                                           pk_column='col1'),
                            ModelSignature(model_name='TestModel',
                                           table_name='testmodel',
                                           pk_column='col2'))

    def test_ne_with_different_field_sigs(self):
        """Testing ModelSignature.__ne__ with different field signatures"""
        model_sig1 = ModelSignature(model_name='TestModel',
                                    table_name='testmodel')
        model_sig1.add_field_sig(FieldSignature.from_field(
            SignatureDefaultsModel._meta.get_field('char_field')))
        model_sig1.add_field_sig(FieldSignature.from_field(
            SignatureDefaultsModel._meta.get_field('dec_field')))

        model_sig2 = ModelSignature(model_name='TestModel',
                                    table_name='testmodel')
        model_sig1.add_field_sig(FieldSignature.from_field(
            SignatureDefaultsModel._meta.get_field('char_field')))

        self.assertNotEqual(model_sig1, model_sig2)


class IndexSignatureTests(BaseSignatureTestCase):
    """Unit tests for IndexSignature."""

    @requires_meta_indexes
    def test_from_index(self):
        """Testing IndexSignature.from_index"""
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

    def test_deserialize_v2(self):
        """Testing IndexSignature.deserialize (signature v2)"""
        index_sig = IndexSignature.deserialize(
            {
                'name': 'index1',
                'fields': ['field1', 'field2'],
            },
            sig_version=2)

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

    def test_serialize_v2(self):
        """Testing IndexSignature.serialize (signature v2)"""
        index_sig = IndexSignature(name='index1', fields=['field1', 'field2'])

        self.assertEqual(
            index_sig.serialize(sig_version=2),
            {
                'name': 'index1',
                'fields': ['field1', 'field2'],
            })

    def test_serialize_v2_without_name(self):
        """Testing IndexSignature.serialize (signature v2) without index name
        """
        index_sig = IndexSignature(fields=['field1', 'field2'])

        self.assertEqual(
            index_sig.serialize(sig_version=2),
            {
                'fields': ['field1', 'field2'],
            })

    def test_eq(self):
        """Testing IndexSignature.__eq__"""
        self.assertEqual(IndexSignature(fields=['field1', 'field2']),
                         IndexSignature(fields=['field1', 'field2']))

        self.assertEqual(IndexSignature(name='test_index',
                                        fields=['field1', 'field2']),
                         IndexSignature(name='test_index',
                                        fields=['field1', 'field2']))

    def test_ne_with_different_names(self):
        """Testing IndexSignature.__ne__ with different names"""
        self.assertNotEqual(IndexSignature(name='index1',
                                           fields=['field1', 'field2']),
                            IndexSignature(name='index2',
                                           fields=['field1', 'field2']))

        self.assertNotEqual(IndexSignature(fields=['field1', 'field2']),
                            IndexSignature(name='index1',
                                           fields=['field1', 'field2']))

    def test_ne_with_different_fields(self):
        """Testing IndexSignature.__ne__ with different fields"""
        self.assertNotEqual(IndexSignature(name='index1',
                                           fields=['field1', 'field2']),
                            IndexSignature(name='index1',
                                           fields=['field2']))

        self.assertNotEqual(IndexSignature(fields=['field1', 'field2']),
                            IndexSignature(fields=['field2']))

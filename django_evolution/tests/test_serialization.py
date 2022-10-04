# coding: utf-8
"""Unit tests for the serialization-related functionality.

Version Added:
    2.2
"""

from __future__ import unicode_literals

from collections import OrderedDict
from unittest import SkipTest

from django.db.models import CharField, F, Q

try:
    # Django >= 3.1
    from django.db.models import Deferrable
except ImportError:
    # Django <= 3.0
    Deferrable = None

from django_evolution.compat import six
from django_evolution.placeholders import NullFieldInitialCallback
from django_evolution.serialization import (CombinedExpression,
                                            deserialize_from_signature,
                                            serialize_to_python,
                                            serialize_to_signature)
from django_evolution.tests.base_test_case import TestCase
from django_evolution.tests.utils import (F_EXPRESSIONS_TYPE,
                                          VALUE_EXPRESSIONS_TYPE)


can_test_combined_expressions = (CombinedExpression is not None and
                                 hasattr(CombinedExpression, 'deconstruct'))


class MyDeconstructableObject(object):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def deconstruct(self):
        return (
            '%s.%s' % (__name__, type(self).__name__),
            self.args,
            self.kwargs,
        )

    def __eq__(self, other):
        return self.args == other.args and self.kwargs == other.kwargs


class DeserializeFromSignatureTests(TestCase):
    """Unit tests for deserialize_from_signature."""

    def test_with_bool(self):
        """Testing deserialize_from_signature with bool"""
        self.assertIs(deserialize_from_signature(True), True)

    def test_with_combined_expression_and_django_lte_4(self):
        """Testing deserialize_from_signature with CombinedExpression using
        Django <= 4.0 signature
        """
        if not can_test_combined_expressions:
            raise SkipTest('Not supported on this version of Django')

        self.assertEqual(
            deserialize_from_signature({
                '_deconstructed': True,
                'args': (
                    {
                        '_deconstructed': True,
                        'args': ('a',),
                        'kwargs': {},
                        'type': 'django.db.models.expressions.F',
                    },
                    '+',
                    {
                        '_deconstructed': True,
                        'args': (1,),
                        'kwargs': {},
                        'type': 'django.db.models.expressions.Value',
                    },
                ),
                'kwargs': {},
                'type': 'django.db.models.expressions.CombinedExpression',
            }),
            F('a') + 1)

    def test_with_combined_expression_and_django_gte_4_1(self):
        """Testing deserialize_from_signature with CombinedExpression using
        Django >= 4.1 signature
        """
        if not can_test_combined_expressions:
            raise SkipTest('Not supported on this version of Django')

        self.assertEqual(
            deserialize_from_signature({
                '_deconstructed': True,
                'args': (
                    {
                        '_deconstructed': True,
                        'args': ('a',),
                        'kwargs': {},
                        'type': 'django.db.models.F',
                    },
                    '+',
                    {
                        '_deconstructed': True,
                        'args': (1,),
                        'kwargs': {},
                        'type': 'django.db.models.Value',
                    },
                ),
                'kwargs': {},
                'type': 'django.db.models.expressions.CombinedExpression',
            }),
            F('a') + 1)

    def test_with_dict(self):
        """Testing deserialize_from_signature with dict"""
        self.assertEqual(
            deserialize_from_signature({
                'a': 'value1',
                'c': [1, 2, 3],
                'b': {
                    'nested': None,
                },
            }),
            {
                'a': 'value1',
                'c': [1, 2, 3],
                'b': {
                    'nested': None,
                },
            })

    def test_with_deconstructable_obj(self):
        """Testing deserialize_from_signature with deconstructable object"""
        self.assertEqual(
            deserialize_from_signature({
                '_deconstructed': True,
                'args': (1, 2, 3),
                'kwargs': {
                    'kwarg1': 'value1',
                    'kwarg2': 'value2',
                },
                'type': ('django_evolution.tests.test_serialization.'
                         'MyDeconstructableObject'),
            }),
            MyDeconstructableObject(1, 2, 3,
                                    kwarg1='value1',
                                    kwarg2='value2'))

    def test_with_deferrable(self):
        """Testing deserialize_from_signature with Deferrable enum value"""
        if Deferrable is None:
            raise SkipTest('Not supported on this version of Django')

        self.assertEqual(
            deserialize_from_signature({
                '_enum': True,
                'type': 'django.db.models.Deferrable',
                'value': 'DEFERRED',
            }),
            Deferrable.DEFERRED)

    def test_with_float(self):
        """Testing deserialize_from_signature with float"""
        self.assertEqual(deserialize_from_signature(1.23), 1.23)

    def test_with_int(self):
        """Testing deserialize_from_signature with int"""
        self.assertEqual(deserialize_from_signature(123), 123)

    def test_with_list(self):
        """Testing deserialize_from_signature with list"""
        self.assertEqual(deserialize_from_signature([1, 2, 'foo']),
                         [1, 2, 'foo'])

    def test_with_long(self):
        """Testing deserialize_from_signature with long"""
        if not six.PY2:
            raise SkipTest('Applicable on Python 2 only.')

        self.assertEqual(deserialize_from_signature(long(123)), long(123))

    def test_with_none(self):
        """Testing deserialize_from_signature with None"""
        self.assertIsNone(deserialize_from_signature(None))

    def test_with_ordered_dict(self):
        """Testing deserialize_from_signature with dict"""
        d = OrderedDict()
        d['a'] = 'value1'
        d['c'] = [1, 2, 3]
        d['b'] = None

        result = deserialize_from_signature(d)
        self.assertIsInstance(result, dict)
        self.assertEqual(
            result,
            {
                'a': 'value1',
                'c': [1, 2, 3],
                'b': None,
            })

    def test_with_placeholder(self):
        """Testing deserialize_from_signature with BasePlaceholder subclass"""
        with self.assertRaises(NotImplementedError):
            deserialize_from_signature(NullFieldInitialCallback())

    def test_with_q(self):
        """Testing deserialize_from_signature with Q"""
        self.assertEqual(
            deserialize_from_signature({
                '_deconstructed': True,
                'args': [
                    {
                        '_deconstructed': True,
                        'args': [
                            ['field1', True],
                        ],
                        'kwargs': {
                            '_negated': True,
                        },
                        'type': 'django.db.models.Q',
                    },
                    {
                        '_deconstructed': True,
                        'args': [
                            ['field2', 'test'],
                            ['field3__gte', 1],
                        ],
                        'kwargs': {
                            '_connector': 'OR',
                        },
                        'type': 'django.db.models.Q'
                    },
                ],
                'kwargs': {},
                'type': 'django.db.models.Q',
            }),
            ~Q(field1=True) & (Q(field2='test') | Q(field3__gte=1)))

    def test_with_q_kwargs(self):
        """Testing deserialize_from_signature with Q and fields in kwargs"""
        self.assertEqual(
            deserialize_from_signature({
                '_deconstructed': True,
                'args': [],
                'kwargs': {
                    'field1': True,
                    '_negated': True,
                },
                'type': 'django.db.models.Q',
            }),
            ~Q(field1=True))

    def test_with_q_empty(self):
        """Testing deserialize_from_signature with empty Q"""
        self.assertEqual(
            deserialize_from_signature({
                '_deconstructed': True,
                'args': [],
                'kwargs': {},
                'type': 'django.db.models.Q',
            }),
            Q())

    def test_with_set(self):
        """Testing deserialize_from_signature with set"""
        self.assertEqual(deserialize_from_signature({1, 3, 2}),
                         {1, 2, 3})

    def test_with_tuple(self):
        """Testing deserialize_from_signature with tuple"""
        self.assertEqual(deserialize_from_signature((1, True, 'foo')),
                         (1, True, 'foo'))

    def test_with_type(self):
        """Testing deserialize_from_signature with type"""
        with self.assertRaises(NotImplementedError):
            deserialize_from_signature(CharField)

    def test_with_unicode_str(self):
        """Testing deserialize_from_signature with unicode string"""
        self.assertEqual(deserialize_from_signature('test 🧸'), 'test 🧸')


class SerializeToPythonTests(TestCase):
    """Unit tests for serialize_to_python."""

    def test_with_bool(self):
        """Testing serialize_to_python with bool"""
        self.assertEqual(serialize_to_python(True), 'True')

    def test_with_byte_str(self):
        """Testing serialize_to_python with byte string"""
        self.assertEqual(serialize_to_signature('test 🧸'.encode('utf-8')),
                         'test \U0001f9f8')

    def test_with_combined_expression(self):
        """Testing serialize_to_python with CombinedExpression"""
        if not can_test_combined_expressions:
            raise SkipTest('Not supported on this version of Django')

        value = F('a') + 1
        self.assertIsInstance(value, CombinedExpression)

        self.assertEqual(serialize_to_python(value),
                         "models.F('a') + models.Value(1)")

    def test_with_dict(self):
        """Testing serialize_to_python with dict"""
        self.assertEqual(
            serialize_to_python({
                'a': 'value1',
                'c': [1, 2, 3],
                'b': {
                    'nested': None,
                },
            }),
            "{'a': 'value1', 'b': {'nested': None}, 'c': [1, 2, 3]}")

    def test_with_deconstructable_obj(self):
        """Testing serialize_to_python with deconstructable object"""
        self.assertEqual(
            serialize_to_python(MyDeconstructableObject(1, 2, 3,
                                                        kwarg1='value1',
                                                        kwarg2='value2')),
            "MyDeconstructableObject(1, 2, 3, kwarg1='value1',"
            " kwarg2='value2')")

    def test_with_deferrable(self):
        """Testing serialize_to_python with Deferrable enum value"""
        if Deferrable is None:
            raise SkipTest('Not supported on this version of Django')

        self.assertEqual(
            serialize_to_python(Deferrable.DEFERRED),
            'models.Deferrable.DEFERRED')

    def test_with_float(self):
        """Testing serialize_to_python with float"""
        self.assertEqual(serialize_to_python(1.23), '1.23')

    def test_with_int(self):
        """Testing serialize_to_python with int"""
        self.assertEqual(serialize_to_python(123), '123')

    def test_with_list(self):
        """Testing serialize_to_python with list"""
        self.assertEqual(serialize_to_python([1, 2, 'foo']),
                         "[1, 2, 'foo']")

    def test_with_long(self):
        """Testing serialize_to_python with long"""
        if not six.PY2:
            raise SkipTest('Applicable on Python 2 only.')

        self.assertEqual(serialize_to_python(long(123)), '123L')

    def test_with_none(self):
        """Testing serialize_to_python with None"""
        self.assertEqual(serialize_to_python(None), 'None')

    def test_with_ordered_dict(self):
        """Testing serialize_to_python with dict"""
        d = OrderedDict()
        d['a'] = 'value1'
        d['c'] = [1, 2, 3]
        d['b'] = None

        self.assertEqual(serialize_to_python(d),
                         "{'a': 'value1', 'c': [1, 2, 3], 'b': None}")

    def test_with_placeholder(self):
        """Testing serialize_to_python with BasePlaceholder subclass"""
        self.assertEqual(serialize_to_python(NullFieldInitialCallback()),
                         '<<USER VALUE REQUIRED>>')

    def test_with_q(self):
        """Testing serialize_to_python with Q"""
        q = (~Q(field1=True) & (Q(field2='test') | Q(field3__gte=1)))

        self.assertEqual(
            serialize_to_python(q),
            "(~models.Q(field1=True) & "
            "(models.Q(field2='test') | "
            "models.Q(field3__gte=1)))")

    def test_with_q_empty(self):
        """Testing serialize_to_python with empty Q"""
        self.assertEqual(serialize_to_python(Q()), 'models.Q()')

    def test_with_set(self):
        """Testing serialize_to_python with set"""
        self.assertEqual(serialize_to_python({1, 3, 2}),
                         "{1, 2, 3}")

    def test_with_tuple(self):
        """Testing serialize_to_python with tuple"""
        self.assertEqual(serialize_to_python((1, True, 'foo')),
                         "(1, True, 'foo')")

    def test_with_type(self):
        """Testing serialize_to_python with type"""
        self.assertEqual(serialize_to_python(OrderedDict), 'OrderedDict')

    def test_with_type_django_model_path(self):
        """Testing serialize_to_python with type containing django.db.models
        module path
        """
        self.assertEqual(serialize_to_python(CharField), 'models.CharField')

    def test_with_unicode_str(self):
        """Testing serialize_to_python with unicode string"""
        self.assertEqual(serialize_to_python('tést'), "'tést'")


class SerializeToSignatureTests(TestCase):
    """Unit tests for serialize_to_signature."""

    def test_with_bool(self):
        """Testing serialize_to_signature with bool"""
        self.assertIs(serialize_to_signature(True), True)

    def test_with_byte_str(self):
        """Testing serialize_to_signature with byte string"""
        self.assertEqual(serialize_to_signature('test 🧸'.encode('utf-8')),
                         'test \U0001f9f8')

    def test_with_combined_expression(self):
        """Testing serialize_to_signature with CombinedExpression"""
        if not can_test_combined_expressions:
            raise SkipTest('Not supported on this version of Django')

        value = F('a') + 1
        self.assertIsInstance(value, CombinedExpression)

        self.assertEqual(
            serialize_to_signature(value),
            {
                '_deconstructed': True,
                'args': (
                    {
                        '_deconstructed': True,
                        'args': ('a',),
                        'kwargs': {},
                        'type': F_EXPRESSIONS_TYPE,
                    },
                    '+',
                    {
                        '_deconstructed': True,
                        'args': (1,),
                        'kwargs': {},
                        'type': VALUE_EXPRESSIONS_TYPE,
                    },
                ),
                'kwargs': {},
                'type': 'django.db.models.expressions.CombinedExpression',
            })

    def test_with_dict(self):
        """Testing serialize_to_signature with dict"""
        self.assertEqual(
            serialize_to_signature({
                'a': 'value1',
                'c': [1, 2, 3],
                'b': {
                    'nested': None,
                },
            }),
            {
                'a': 'value1',
                'c': [1, 2, 3],
                'b': {
                    'nested': None,
                },
            })

    def test_with_deconstructable_obj(self):
        """Testing serialize_to_signature with deconstructable object"""
        self.assertEqual(
            serialize_to_signature(MyDeconstructableObject(1, 2, 3,
                                                           kwarg1='value1',
                                                           kwarg2='value2')),
            {
                '_deconstructed': True,
                'args': (1, 2, 3),
                'kwargs': {
                    'kwarg1': 'value1',
                    'kwarg2': 'value2',
                },
                'type': ('django_evolution.tests.test_serialization.'
                         'MyDeconstructableObject'),
            })

    def test_with_deferrable(self):
        """Testing serialize_to_signature with Deferrable enum value"""
        if Deferrable is None:
            raise SkipTest('Not supported on this version of Django')

        self.assertEqual(
            serialize_to_signature(Deferrable.DEFERRED),
            {
                '_enum': True,
                'type': 'django.db.models.constraints.Deferrable',
                'value': 'DEFERRED',
            })

    def test_with_float(self):
        """Testing serialize_to_signature with float"""
        self.assertEqual(serialize_to_signature(1.23), 1.23)

    def test_with_int(self):
        """Testing serialize_to_signature with int"""
        self.assertEqual(serialize_to_signature(123), 123)

    def test_with_list(self):
        """Testing serialize_to_signature with list"""
        self.assertEqual(serialize_to_signature([1, 2, 'foo']),
                         [1, 2, 'foo'])

    def test_with_long(self):
        """Testing serialize_to_signature with long"""
        if not six.PY2:
            raise SkipTest('Applicable on Python 2 only.')

        self.assertEqual(serialize_to_signature(long(123)), long(123))

    def test_with_none(self):
        """Testing serialize_to_signature with None"""
        self.assertIsNone(serialize_to_signature(None))

    def test_with_ordered_dict(self):
        """Testing serialize_to_signature with dict"""
        d = OrderedDict()
        d['a'] = 'value1'
        d['c'] = [1, 2, 3]
        d['b'] = None

        result = serialize_to_signature(d)
        self.assertIsInstance(result, dict)
        self.assertEqual(
            result,
            {
                'a': 'value1',
                'c': [1, 2, 3],
                'b': None,
            })

    def test_with_placeholder(self):
        """Testing serialize_to_signature with BasePlaceholder subclass"""
        with self.assertRaises(NotImplementedError):
            serialize_to_signature(NullFieldInitialCallback())

    def test_with_q(self):
        """Testing serialize_to_signature with Q"""
        q = (~Q(field1=True) & (Q(field2='test') | Q(field3__gte=1)))

        self.assertEqual(
            serialize_to_signature(q),
            {
                '_deconstructed': True,
                'args': [
                    {
                        '_deconstructed': True,
                        'args': [
                            ('field1', True),
                        ],
                        'kwargs': {
                            '_negated': True,
                        },
                        'type': 'django.db.models.Q',
                    },
                    {
                        '_deconstructed': True,
                        'args': [
                            ('field2', 'test'),
                            ('field3__gte', 1),
                        ],
                        'kwargs': {
                            '_connector': 'OR',
                        },
                        'type': 'django.db.models.Q'
                    },
                ],
                'kwargs': {},
                'type': 'django.db.models.Q',
            })

    def test_with_q_empty(self):
        """Testing serialize_to_signature with empty Q"""
        self.assertEqual(
            serialize_to_signature(Q()),
            {
                '_deconstructed': True,
                'args': [],
                'kwargs': {},
                'type': 'django.db.models.Q',
            })

    def test_with_set(self):
        """Testing serialize_to_signature with set"""
        self.assertEqual(serialize_to_signature({1, 3, 2}),
                         {1, 2, 3})

    def test_with_tuple(self):
        """Testing serialize_to_signature with tuple"""
        self.assertEqual(serialize_to_signature((1, True, 'foo')),
                         (1, True, 'foo'))

    def test_with_type(self):
        """Testing serialize_to_signature with type"""
        with self.assertRaises(NotImplementedError):
            serialize_to_signature(CharField)

    def test_with_unicode_str(self):
        """Testing serialize_to_signature with unicode string"""
        self.assertEqual(serialize_to_signature('test 🧸'), 'test 🧸')

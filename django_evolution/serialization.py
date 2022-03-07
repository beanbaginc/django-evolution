"""Serialization and deserialization.

These classes are responsible for converting objects/values to signature data
or to Python code (for evolution hints), and for converting signature data back
to objects.

The classes in this file are considered private API. The only public API is:

* :py:func:`deserialize_from_python`
* :py:func:`serialize_to_signature`
* :py:func:`serialize_to_python`

Version Added:
    2.2
"""

from __future__ import unicode_literals

import inspect
from collections import OrderedDict
from copy import deepcopy
from importlib import import_module

try:
    from enum import Enum
except ImportError:
    Enum = None

from django.db.models import Q

try:
    # Django >= 3.1
    from django.db.models import Deferrable
except ImportError:
    # Django <= 3.0
    Deferrable = None

try:
    # Django >= 1.8
    from django.db.models.expressions import CombinedExpression
except ImportError:
    # Django <= 1.7
    CombinedExpression = None

from django_evolution.compat import six
from django_evolution.placeholders import BasePlaceholder


_deconstructed_serialization_map = {}
_serialization_map = {}


class BaseSerialization(object):
    """Base class for serialization.

    Subclasses should override the methods within this class to provide
    serialization and deserialization logic specific to one or more types.

    Version Added:
        2.2
    """

    @classmethod
    def serialize_to_signature(cls, value):
        """Serialize a value to JSON-compatible signature data.

        Args:
            value (object or type):
                The value to serialize.

        Returns:
            object:
            The resulting signature data.
        """
        raise NotImplementedError

    @classmethod
    def serialize_to_python(cls, value):
        """Serialize a value to a Python code string.

        Args:
            value (object or type):
                The value to serialize.

        Returns:
            unicode:
            The resulting Python code.
        """
        raise NotImplementedError

    @classmethod
    def deserialize_from_signature(cls, payload):
        """Deserialize signature data to a value.

        Args:
            payload (object):
                The payload to deserialize.

        Returns:
            object or type:
            The resulting value.
        """
        raise NotImplementedError

    @classmethod
    def deserialize_from_deconstructed(cls, type_cls, args, kwargs):
        """Deserialize an object from deconstructed object information.

        Args:
            type_cls (type):
                The type of object to construct.

            args (tuple):
                The positional arguments passed to the constructor.

            kwargs (dict):
                The keyword arguments passed to the constructor.

        Returns:
            object:
            The resulting object.
        """
        raise NotImplementedError


class BaseIterableSerialization(BaseSerialization):
    """Base class for iterable types.

    This will handle the signature-related serialization/deserialization
    automatically, based on :py:attr:`iterable_type`.

    Version Added:
        2.2
    """

    #: The type used to store items.
    #:
    #: Type:
    #:     type
    item_type = None

    @classmethod
    def serialize_to_signature(cls, value):
        """Serialize a value to JSON-compatible signature data.

        Args:
            value (object or type):
                The value to serialize.

        Returns:
            object:
            The resulting signature data.
        """
        return cls.item_type(
            serialize_to_signature(_item)
            for _item in value
        )

    @classmethod
    def deserialize_from_signature(cls, payload):
        """Deserialize signature data to a value.

        Args:
            payload (object):
                The payload to deserialize.

        Returns:
            object or type:
            The resulting value.
        """
        return cls.item_type(
            deserialize_from_signature(_item)
            for _item in payload
        )


class PrimitiveSerialization(BaseSerialization):
    """Base class for serialization for Python primitives.

    This will wrap simple values, deep-copying them when storing as signature
    data, returning a :py:func:`repr` result when converting to Python code,
    and using the value as-is when deserializing.

    Version Added:
        2.2
    """

    @classmethod
    def serialize_to_signature(cls, value):
        """Serialize a value to JSON-compatible signature data.

        Args:
            value (object):
                The value to serialize.

        Returns:
            object:
            A deep copy of the provided value.
        """
        return deepcopy(value)

    @classmethod
    def serialize_to_python(cls, value):
        return repr(value)

    @classmethod
    def deserialize_from_signature(cls, payload):
        """Deserialize signature data to a value.

        This will just return the value as-is.

        Args:
            payload (object):
                The payload to deserialize.

        Returns:
            object or type:
            The resulting value.
        """
        return payload


class ClassSerialization(BaseSerialization):
    """Base class for serialization for classes.

    This is able to serialize a class name to Python. It cannot be used for
    signature data.

    Version Added:
        2.2
    """

    @classmethod
    def serialize_to_python(cls, value):
        if value.__module__.startswith('django.db.models'):
            prefix = 'models.'
        else:
            prefix = ''

        return '%s%s' % (prefix, value.__name__)


class DictSerialization(BaseSerialization):
    """Base class for serialization for dictionaries.

    This will be used for plain :py:class:`dict` instances and for
    :py:class:`collections.OrderedDict`.

    Version Added:
        2.2
    """

    @classmethod
    def serialize_to_signature(cls, value):
        """Serialize a dictionary to JSON-compatible signature data.

        Args:
            value (dict):
                The dictionary to serialize.

        Returns:
            dict:
            The resulting dictionary.
        """
        return {
            _key: serialize_to_signature(_value)
            for _key, _value in six.iteritems(value)
        }

    @classmethod
    def serialize_to_python(cls, value):
        """Serialize a dictionary to a Python code string.

        Args:
            value (dict):
                The dictionary to serialize.

        Returns:
            unicode:
            The resulting Python code.
        """
        if isinstance(value, OrderedDict):
            items = six.iteritems(value)
        else:
            items = sorted(six.iteritems(value),
                           key=lambda pair: pair[0])

        return '{%s}' % ', '.join(
            '%s: %s' % (serialize_to_python(_key),
                        serialize_to_python(_value))
            for _key, _value in items
        )

    @classmethod
    def deserialize_from_signature(cls, payload):
        """Deserialize dictionary signature data to a value.

        Args:
            payload (dict):
                The payload to deserialize.

        Returns:
            dict:
            The resulting value.
        """
        return {
            _key: deserialize_from_signature(_value)
            for _key, _value in six.iteritems(payload)
        }


class EnumSerialization(BaseSerialization):
    """Serialization for enums.

    Version Added:
        2.2
    """

    @classmethod
    def serialize_to_signature(cls, value):
        """Serialize a value to JSON-compatible signature data.

        Args:
            value (object):
                The value to serialize.

        Returns:
            object:
            A deep copy of the provided value.
        """
        cls = type(value)

        return {
            '_enum': True,
            'type': '%s.%s' % (cls.__module__, cls.__name__),
            'value': value._name_,
        }

    @classmethod
    def serialize_to_python(cls, value):
        """Serialize an enum value to a Python code string.

        Args:
            value (enum.Enum):
                The enum value to serialize.

        Returns:
            unicode:
            The resulting Python code.
        """
        cls = type(value)
        cls_name = cls.__name__
        mod_name = cls.__module__

        if mod_name.startswith('django.db.models'):
            cls_path = 'models.%s' % cls_name
        else:
            cls_path = '%s.%s' % (mod_name, cls_name)

        return '%s.%s' % (cls_path, value._name_)

    @classmethod
    def deserialize_from_signature(cls, payload):
        """Deserialize signature data to a value.

        This will just return the value as-is.

        Args:
            payload (object):
                The payload to deserialize.

        Returns:
            object or type:
            The resulting value.
        """
        cls_path = payload.get('type')
        value = payload.get('value')

        cls_module, cls_name = cls_path.rsplit('.', 1)

        try:
            cls_type = getattr(import_module(cls_module), cls_name)
        except (AttributeError, ImportError):
            raise ImportError('Unable to locate enum type %s' % cls_path)

        return cls_type[value]


class ListSerialization(BaseIterableSerialization):
    """Base class for serialization for lists.

    Version Added:
        2.2
    """

    item_type = list

    @classmethod
    def serialize_to_python(cls, value):
        """Serialize a list to a Python code string.

        Args:
            value (list):
                The list to serialize.

        Returns:
            unicode:
            The resulting Python code.
        """
        return '[%s]' % ', '.join(
            serialize_to_python(_item)
            for _item in value
        )


class TupleSerialization(BaseIterableSerialization):
    """Base class for serialization for tuples.

    Version Added:
        2.2
    """

    item_type = tuple

    @classmethod
    def serialize_to_python(cls, value):
        """Serialize a tuple to a Python code string.

        Args:
            value (tuple):
                The tuple to serialize.

        Returns:
            unicode:
            The resulting Python code.
        """
        if len(value) == 1:
            suffix = ','
        else:
            suffix = ''

        return '(%s%s)' % (
            ', '.join(
                serialize_to_python(_item)
                for _item in value
            ),
            suffix)


class SetSerialization(BaseIterableSerialization):
    """Base class for serialization for sets.

    Version Added:
        2.2
    """

    item_type = set

    @classmethod
    def serialize_to_python(cls, value):
        """Serialize a set to a Python code string.

        Args:
            value (set):
                The set to serialize.

        Returns:
            unicode:
            The resulting Python code.
        """
        return '{%s}' % ', '.join(
            serialize_to_python(_item)
            for _item in sorted(value)
        )


class StringSerialization(PrimitiveSerialization):
    """Base class for serialization for strings.

    This will encode to a string, and ensure the results are consistent
    across Python 2 and 3.

    Version Added:
        2.2
    """

    @classmethod
    def serialize_to_signature(cls, value):
        """Serialize a string to JSON-compatible string.

        Args:
            value (bytes or unicode):
                The string to serialize. If a byte string, it's expected to
                contain UTF-8 data.

        Returns:
            unicode:
            The resulting string.
        """
        if isinstance(value, bytes):
            value = value.decode('utf-8')

        return value

    @classmethod
    def serialize_to_python(cls, value):
        """Serialize a string to a Python code string.

        Args:
            value (bytes or unicode):
                The string to serialize. If a byte string, it's expected to
                contain UTF-8 data.

        Returns:
            unicode:
            The resulting Python code.
        """
        if isinstance(value, bytes):
            value = value.decode('utf-8')

        result = repr(value)

        if six.PY2 and result.startswith('u'):
            # Make sure we're getting the real Unicode values out, and not
            # string escapes.
            #
            # Users will need to add a "coding: utf-8" to the file, if
            # Unicode characters are present and they care about support
            # for Python 2.7.
            result = result[1:].decode('unicode-escape')

        return result


class DeconstructedSerialization(BaseSerialization):
    """Base class for serialization for objects supporting deconstruction.

    This is used for Django objects that support a ``deconstruct()`` method.
    It will convert to/from deconstructed signature data, and provide a
    suitable representation in Python.

    Version Added:
        2.2
    """

    @classmethod
    def serialize_to_signature(cls, value):
        """Serialize a value to JSON-compatible signature data.

        This will deconstruct the object and return a dictionary containing
        the deconstructed information and a flag noting that it must be
        reconstructed.

        Args:
            value (object or type):
                The value to serialize.

        Returns:
            object:
            The resulting signature data.
        """
        cls_path, args, kwargs = cls._deconstruct_object(value)

        return {
            '_deconstructed': True,
            'args': serialize_to_signature(args) or (),
            'kwargs': serialize_to_signature(kwargs),
            'type': cls_path,
        }

    @classmethod
    def serialize_to_python(cls, value):
        """Serialize an object to a Python code string.

        This will generate code that constructs an instance of the object.

        Args:
            value (object):
                The object to serialize.

        Returns:
            unicode:
            The resulting Python code.
        """
        cls_path, args, kwargs = cls._deconstruct_object(value)
        module_path, cls_name = cls_path.rsplit('.', 1)

        if cls_path.startswith('django.db.models'):
            cls_name = 'models.%s' % cls_name

        all_args = []

        if args:
            all_args += [
                serialize_to_python(_arg)
                for _arg in args
            ]

        if kwargs:
            all_args += [
                '%s=%s' % (_key, serialize_to_python(_value))
                for _key, _value in sorted(six.iteritems(kwargs),
                                           key=lambda pair: pair[0])
            ]

        return '%s(%s)' % (cls_name, ', '.join(all_args))

    @classmethod
    def deserialize_from_signature(cls, payload):
        """Deserialize deconstructed dictionary signature data to an object.

        This will attempt to re-construct an object from the deconstructed
        signature data. This may fail if there is any issue looking up or
        instantiating the object.

        Args:
            payload (dict):
                The payload to deserialize.

        Returns:
            dict:
            The resulting value.

        Raises:
            Exception:
                An unexpected error occurred when instantiating the object.

            ImportError:
                The class specified in the signature data could not be
                imported.
        """
        cls_type, args, kwargs = cls._deserialize_deconstructed(payload)

        if cls_type in _deconstructed_serialization_map:
            serialization = _deconstructed_serialization_map[cls_type]

            try:
                return serialization.deserialize_from_deconstructed(
                    cls_type, args, kwargs)
            except NotImplementedError:
                # This doesn't provide explicit deserialization. Fall back
                # on defaults.
                pass

        # Let any exception bubble up.
        return cls_type(*args, **kwargs)

    @classmethod
    def _deconstruct_object(cls, obj):
        """Deconstruct an object.

        This can be overridden by subclasses to work around lack of
        deconstruction support on earlier versions of Django.

        Args:
            obj (object):
                The object to deconstruct.
        """
        if not hasattr(obj, 'deconstruct'):
            raise NotImplementedError(
                '%s.deconstruct() is not available on this version of '
                'Django. Subclases of the serializer should override '
                '_deconstruct_object to support this.')

        return obj.deconstruct()

    @classmethod
    def _deserialize_deconstructed(cls, payload):
        """Deserialize a deconstructed object payload.

        Args:
            payload (dict):
                The payload representing a deconstructed object.

        Returns:
            tuple:
            A tuple containing:

            1. The object class.
            2. Positional arguments to pass to the constructor.
            3. Keyword arguments to pass to the constructor,
        """
        cls_path = payload['type']
        cls_module, cls_name = cls_path.rsplit('.', 1)

        try:
            cls_type = getattr(import_module(cls_module), cls_name)
        except (AttributeError, ImportError):
            raise ImportError('Unable to locate value type %s' % cls_path)

        args = tuple(
            deserialize_from_signature(_arg_value)
            for _arg_value in payload['args']
        )

        kwargs = {
            _key: deserialize_from_signature(_arg_value)
            for _key, _arg_value in six.iteritems(payload['kwargs'])
        }

        return cls_type, args, kwargs


class PlaceholderSerialization(BaseSerialization):
    """Base class for serialization for a placeholder object.

    Version Added:
        2.2
    """

    @classmethod
    def serialize_to_python(cls, value):
        """Serialize a placeholder object to a Python code string.

        Args:
            value (django_evolution.placeholders.BasePlaceholder):
                The object to serialize.

        Returns:
            unicode:
            The resulting Python code.
        """
        return repr(value)


class CombinedExpressionSerialization(DeconstructedSerialization):
    """Base class for serialization for CombinedExpression objects.

    This ensures a consistent representation of
    :py:class:`django.db.models.CombinedExpression` objects across all
    supported versions of Django.

    Note that while this can technically be used in version of Django prior
    to 2.0, many of the objects nested within won't be supported. In practice,
    database features really start to make use of this in a way that impacts
    serialization code in Django 2.0 and higher.

    Version Added:
        2.2
    """

    @classmethod
    def serialize_to_python(cls, value):
        """Serialize a CombinedExpression object to a Python code string.

        Args:
            value (object):
                The object to serialize.

        Returns:
            unicode:
            The resulting Python code.
        """
        return '%s %s %s' % (
            serialize_to_python(value.lhs),
            value.connector,
            serialize_to_python(value.rhs),
        )

    @classmethod
    def _deconstruct_object(cls, obj):
        """Deconstruct a CombinedExpression.

        Args:
            obj (django.db.models.expressions.CombinedExpression):
                The object to deconstruct.
        """
        if hasattr(obj, 'deconstruct'):
            # Django >= 2.0
            return (
                super(CombinedExpressionSerialization, cls)
                ._deconstruct_object(obj)
            )
        else:
            # Django <= 1.11
            return (
                '%s.%s' % (CombinedExpression.__module__,
                           CombinedExpression.__name__),
                (
                    serialize_to_signature(obj.lhs),
                    serialize_to_signature(obj.connector),
                    serialize_to_signature(obj.rhs)),
                {},
            )


class QSerialization(DeconstructedSerialization):
    """Base class for serialization for Q objects.

    This ensures a consistent representation of :py:class:`django.db.models.Q`
    objects across all supported versions of Django.

    Django 1.7 through 3.1 encode the data in a different form than 3.2+.
    This ensures serialized data in a form closer to 3.2+'s version, while
    providing compatibility with older versions.

    Version Added:
        2.2
    """

    child_separators = {
        Q.OR: ' | ',
        Q.AND: ' & ',
    }

    @classmethod
    def serialize_to_signature(cls, q):
        """Serialize a Q object to JSON-compatible signature data.

        Args:
            value (object or type):
                The value to serialize.

        Returns:
            object:
            The resulting signature data.
        """
        q_cls = type(q)
        cls_path = '%s.%s' % (q_cls.__module__, q_cls.__name__)

        if cls_path.startswith('django.db.models.query_utils'):
            cls_path = cls_path.replace('django.db.models.query_utils',
                                        'django.db.models')

        args = [
            serialize_to_signature(_child)
            for _child in q.children
        ]

        kwargs = {}

        if q.connector != q.default:
            kwargs['_connector'] = q.connector

        if q.negated:
            kwargs['_negated'] = True

        return {
            '_deconstructed': True,
            'args': args,
            'kwargs': kwargs,
            'type': cls_path,
        }

    @classmethod
    def serialize_to_python(cls, value):
        """Serialize a Q object to a Python code string.

        This will generate code that constructs an instance of the object,
        handling negation, AND/OR connections, and children.

        Args:
            value (object):
                The object to serialize.

        Returns:
            unicode:
            The resulting Python code.
        """
        q = value
        num_children = len(q.children)

        result = []

        if value.negated:
            result.append('~')

        if num_children == 0:
            result.append('models.Q()')
        elif num_children == 1:
            child = value.children[0]

            result.append('models.Q(%s=%s)' % (child[0],
                                               serialize_to_python(child[1])))
        else:
            children = []

            for child in value.children:
                if isinstance(child, tuple):
                    children.append(
                        'models.Q(%s=%s)' % (child[0],
                                             serialize_to_python(child[1])))
                elif isinstance(child, Q):
                    children.append(serialize_to_python(child))
                else:
                    raise TypeError('Unexpected type %s (value %r) in Q()'
                                    % (type(child), child))

            if len(children) == 1:
                result.append(children)
            elif len(children) > 1:
                result.append(
                    '(%s)'
                    % cls.child_separators[value.connector].join(children))

        return ''.join(result)

    @classmethod
    def deserialize_from_deconstructed(cls, type_cls, args, kwargs):
        """Deserialize an object from deconstructed object information.

        Args:
            type_cls (type):
                The type of object to construct.

            args (tuple):
                The positional arguments passed to the constructor.

            kwargs (dict):
                The keyword arguments passed to the constructor.

        Returns:
            object:
            The resulting object.
        """
        norm_keywords = six.PY2

        negated = kwargs.pop('_negated', False)
        connector = kwargs.pop('_connector', Q.default)

        new_args = []

        for arg in args:
            if isinstance(arg, (list, tuple)):
                if norm_keywords:
                    # On Python 2, keyword arguments should be native strings.
                    # This isn't a problem for general usage, but it does
                    # affect the string representation, which assertQEqual()
                    # uses to determine equality.
                    arg = (arg[0].encode('utf-8'), arg[1])

                new_args.append(tuple(arg))
            else:
                new_args.append(arg)

        if norm_keywords:
            # We also need to normalize anything found in kwargs.
            kwargs = {
                str(_key): _value
                for _key, _value in six.iteritems(kwargs)
            }

        q = type_cls(*new_args, **kwargs)
        q.connector = connector

        if negated:
            q.negate()

        return q


def _init_serialization():
    """Initialize the serialization support."""
    global _deconstructed_serialization_map, _serialization_map

    if _deconstructed_serialization_map or _serialization_map:
        return

    _deconstructed_serialization_map = {
        Q: QSerialization,
    }

    if CombinedExpression is not None:
        _deconstructed_serialization_map[CombinedExpression] = \
            CombinedExpressionSerialization

    _serialization_map = {
        # String-based
        bytes: StringSerialization,
        six.text_type: StringSerialization,

        # Dictionary-based
        OrderedDict: DictSerialization,
        dict: DictSerialization,

        # Primitives
        bool: PrimitiveSerialization,
        float: PrimitiveSerialization,
        int: PrimitiveSerialization,
        type(None): PrimitiveSerialization,

        # Iterables
        list: ListSerialization,
        set: SetSerialization,
        tuple: TupleSerialization,

        # Class references
        type: ClassSerialization,
    }

    if six.PY2:
        _serialization_map.update({
            long: PrimitiveSerialization,
        })


def _get_serializer_for_value(value, serializing):
    """Return a serializer for the specified value.

    Version Added:
        2.2

    Args:
        value (object or type):
            The value to serialize.

    Returns:
        type:
        The serializer class. If one could not be found, ``None`` will be
        returned.
    """
    _init_serialization()

    cls = type(value)
    is_class = inspect.isclass(value)

    serialization_cls = None

    if inspect.isclass(value):
        if cls in _serialization_map:
            serialization_cls = _serialization_map[cls]
        elif is_class:
            serialization_cls = ClassSerialization
    else:
        if cls in _deconstructed_serialization_map:
            serialization_cls = _deconstructed_serialization_map[cls]
        elif (Enum is not None and
              (serializing and issubclass(cls, Enum)) or
              (not serializing and
               cls is dict and
               value.get('_enum') is True)):
            serialization_cls = EnumSerialization
        elif serializing and hasattr(value, 'deconstruct'):
            serialization_cls = DeconstructedSerialization
        elif (not serializing and
              cls is dict and
              value.get('_deconstructed') is True):
            serialization_cls = DeconstructedSerialization
        elif isinstance(value, BasePlaceholder):
            serialization_cls = PlaceholderSerialization
        elif cls in _serialization_map:
            serialization_cls = _serialization_map[cls]

    return serialization_cls


def serialize_to_signature(value):
    """Serialize a value to the signature.

    Version Added:
        2.2

    Args:
        value (object or type):
            The value to serialize.

    Returns:
        object:
        The resulting JSON-serializable data.
    """
    serialization_cls = _get_serializer_for_value(value, serializing=True)

    if serialization_cls is None:
        raise TypeError(
            'Unsupported type %s passed to serialize_to_signature(). '
            'Value: %r'
            % (type(value), value))

    return serialization_cls.serialize_to_signature(value)


def serialize_to_python(value):
    """Serialize a value to a Python code string.

    Version Added:
        2.2

    Args:
        value (object or type):
            The value to serialize.

    Returns:
        unicode:
        The resulting Python code string.
    """
    serialization_cls = _get_serializer_for_value(value, serializing=True)

    if serialization_cls is None:
        raise TypeError(
            'Unsupported type %s passed to serialize_to_python(). '
            'Value: %r'
            % (type(value), value))

    return serialization_cls.serialize_to_python(value)


def deserialize_from_signature(payload):
    """Deserialize a value from the signature.

    Version Added:
        2.2

    Args:
        payload (object):
            The payload to deserialize.

    Returns:
        object or type:
        The resulting deserialized value.

    Raises:
        Exception:
            An unexpected error occurred when deserializing. This is specific
            to the type of deserializer.
    """
    serialization_cls = _get_serializer_for_value(payload, serializing=False)

    if serialization_cls is None:
        raise TypeError(
            'Unsupported type %s passed to deserialize_from_signature(). '
            'Value: %r'
            % (type(payload), payload))

    return serialization_cls.deserialize_from_signature(payload)

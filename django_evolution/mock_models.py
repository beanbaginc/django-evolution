"""Utilities for building mock database models and fields."""

from __future__ import unicode_literals

from django.db import models
from django.db.models.base import ModelState
from django.db.models.fields import FieldDoesNotExist
from django.db.models.fields.related import RECURSIVE_RELATIONSHIP_CONSTANT
from django.utils import six
from django.utils.encoding import force_bytes
from django.utils.functional import curry

from django_evolution.compat.datastructures import OrderedDict
from django_evolution.compat.models import (get_remote_field,
                                            get_remote_field_model)


def create_field(proj_sig, field_name, field_type, field_attrs, parent_model):
    """Create a Django field instance for the given signature data.

    This creates a field in a way that's compatible with a variety of versions
    of Django. It takes in data such as the field's name and attributes
    and creates an instance that can be used like any field found on a model.

    Args:
        field_name (unicode):
            The name of the field.

        field_type (cls):
            The class for the type of field being constructed. This must be a
            subclass of :py:class:`django.db.models.Field`.

        field_attrs (dict):
            Attributes to set on the field.

        parent_model (cls):
            The parent model that would own this field. This must be a
            subclass of :py:class:`django.db.models.Model`.

    Returns:
        django.db.models.Field:
        A new field instance matching the provided data.
    """
    # Convert to the standard string format for each version of Python, to
    # simulate what the format would be for the default name.
    field_name = str(field_name)

    # related_model isn't a valid field attribute, so it must be removed
    # prior to instantiating the field, but it must be restored
    # to keep the signature consistent.
    related_model = field_attrs.pop('related_model', None)

    if related_model:
        related_app_name, related_model_name = related_model.split('.')
        related_model_sig = proj_sig[related_app_name][related_model_name]
        to = MockModel(proj_sig, related_app_name, related_model_name,
                       related_model_sig, stub=True)

        if (issubclass(field_type, models.ForeignKey) and
            hasattr(models, 'CASCADE') and
            'on_delete' not in field_attrs):
            # Starting in Django 2.0, on_delete is a requirement for
            # ForeignKeys. If not provided in the signature, we want to
            # default this to CASCADE, which is the value that Django
            # previously defaulted to.
            field_attrs['on_delete'] = models.CASCADE

        field = field_type(to, name=field_name, **field_attrs)
        field_attrs['related_model'] = related_model
    else:
        field = field_type(name=field_name, **field_attrs)

    if field_type is models.ManyToManyField and parent_model is not None:
        # Starting in Django 1.2, a ManyToManyField must have a through
        # model defined. This will be set internally to an auto-created
        # model if one isn't specified. We have to fake that model.
        through_model = field_attrs.get('through_model', None)
        through_model_sig = None

        if through_model:
            through_app_name, through_model_name = through_model.split('.')
            through_model_sig = proj_sig[through_app_name][through_model_name]
        elif hasattr(field, '_get_m2m_attr'):
            # Django >= 1.2
            remote_field = get_remote_field(field)
            remote_field_model = get_remote_field_model(remote_field)

            to = remote_field_model._meta.object_name.lower()

            if (remote_field_model == RECURSIVE_RELATIONSHIP_CONSTANT or
                to == parent_model._meta.object_name.lower()):
                from_ = 'from_%s' % to
                to = 'to_%s' % to
            else:
                from_ = parent_model._meta.object_name.lower()

            # This corresponds to the signature in
            # related.create_many_to_many_intermediary_model
            through_app_name = parent_model.app_name
            through_model_name = '%s_%s' % (parent_model._meta.object_name,
                                            field.name)
            through_model = '%s.%s' % (through_app_name, through_model_name)

            fields = OrderedDict()
            fields['id'] = {
                'field_type': models.AutoField,
                'primary_key': True,
            }

            fields[from_] = {
                'field_type': models.ForeignKey,
                'related_model': '%s.%s' % (parent_model.app_name,
                                            parent_model._meta.object_name),
                'related_name': '%s+' % through_model_name,
            }

            fields[to] = {
                'field_type': models.ForeignKey,
                'related_model': related_model,
                'related_name': '%s+' % through_model_name,
            }

            through_model_sig = {
                'meta': {
                    'db_table': field._get_m2m_db_table(parent_model._meta),
                    'managed': True,
                    'auto_created': True,
                    'app_label': through_app_name,
                    'unique_together': ((from_, to),),
                    'pk_column': 'id',
                },
                'fields': fields,
            }

            field.auto_created = True

        if through_model_sig:
            through = MockModel(proj_sig, through_app_name, through_model_name,
                                through_model_sig)
            get_remote_field(field).through = through

        field.m2m_db_table = curry(field._get_m2m_db_table, parent_model._meta)
        field.set_attributes_from_rel()

    field.set_attributes_from_name(field_name)

    # Needed in Django >= 1.7, for index building.
    field.model = parent_model

    return field


class MockMeta(object):
    """A mock of a models Options object, based on the model signature.

    This emulates the standard Meta class for a model, storing data and
    providing mock functions for setting up fields from a signature.
    """

    def __init__(self, proj_sig, app_name, model_name, model_sig):
        """Initialize the meta instance.

        Args:
            proj_sig (dict):
                The project's schema signature.

            app_name (unicode):
                The name of the Django application owning the model.

            model_name (unicode):
                The name of the model.

            model_sig (dict):
                The model's schema signature.
        """
        self.object_name = model_name
        self.app_label = app_name
        self.meta = {
            'order_with_respect_to': None,
            'has_auto_field': None,
            'db_tablespace': None,
            'swapped': False,
            'index_together': [],
            'indexes': [],
        }
        self.meta.update(model_sig['meta'])
        self._fields = OrderedDict()
        self._many_to_many = OrderedDict()
        self.abstract = False
        self.managed = True
        self.proxy = False
        self._model_sig = model_sig
        self._proj_sig = proj_sig

    @property
    def local_fields(self):
        """A list of all local fields on the model."""
        return list(six.itervalues(self._fields))

    fields = local_fields

    @property
    def local_many_to_many(self):
        """A list of all local Many-to-Many fields on the model."""
        return list(six.itervalues(self._many_to_many))

    def setup_fields(self, model, stub=False):
        """Set up the fields listed in the model's signature.

        For each field in the model signature's list of fields, a field
        instance will be created and stored in :py:attr:`_fields` or
        :py:attr:`_many_to_many` (depending on the type of field).

        Some fields (for instance, a field representing a primary key) may
        also influence the attributes on this model.

        Args:
            model (cls):
                The model class owning this meta instance. This must be a
                subclass of :py:class:`django.db.models.Model`.

            stub (bool, optional):
                If provided, only a primary key will be set up. This is used
                internally when creating relationships between models and
                fields in order to prevent recursive relationships.
        """
        for field_name, field_sig in six.iteritems(self._model_sig['fields']):
            primary_key = field_sig.get('primary_key', False)

            if not stub or primary_key:
                field_type = field_sig.pop('field_type')
                field = create_field(self._proj_sig, field_name, field_type,
                                     field_sig, model)
                field_sig['field_type'] = field_type

                if type(field) is models.AutoField:
                    self.meta['has_auto_field'] = True
                    self.meta['auto_field'] = field

                if type(field) is models.ManyToManyField:
                    self._many_to_many[field.name] = field
                else:
                    self._fields[field.name] = field

                field.set_attributes_from_name(field_name)

                if primary_key:
                    self.pk = field

    def __getattr__(self, name):
        """Return an attribute from the meta class.

        This will look up the attribute from the correct location, depending
        on the attribute being accessed.

        Args:
            name (unicode):
                The attribute name.

        Returns:
            object:
            The attribute value.
        """
        if name == 'model_name':
            return self.object_name

        return self.meta[name]

    def get_field(self, name):
        """Return a field with the given name.

        Args:
            name (unicode):
                The name of the field.

        Returns:
            django.db.models.Field:
            The field with the given name.

        Raises:
            django.db.models.fields.FieldDoesNotExist:
                The field could not be found.
        """
        try:
            return self._fields[name]
        except KeyError:
            try:
                return self._many_to_many[name]
            except KeyError:
                raise FieldDoesNotExist('%s has no field named %r' %
                                        (self.object_name, name))

    def get_field_by_name(self, name):
        """Return information on a field with the given name.

        This is a stub that provides only basic functionality. It will
        return information for a field with the given name, with most
        data hard-coded.

        Args:
            name (unicode):
                The name of the field.

        Returns:
            tuple:
            A tuple of information for the following:

            * The field instance (:py:class:`django.db.models.Field`)
            * The model (hard-coded as ``None``)
            * Whether this field is owned by this model (hard-coded as
              ``True``)
            * Whether this is for a many-to-many relationship (hard-coded as
             ``None``)

        Raises:
            django.db.models.fields.FieldDoesNotExist:
                The field could not be found.
        """
        return (self.get_field(name), None, True, None)


class MockModel(object):
    """A mock model.

    This replicates some of the state and functionality of a model for
    use when generating, reading, or mutating signatures.
    """

    def __init__(self, proj_sig, app_name, model_name, model_sig, stub=False,
                 db_name=None):
        """Initialize the model.

        Args:
            proj_sig (dict):
                The project's schema signature.

            app_name (unicode):
                The name of the Django app that owns the model.

            model_name (unicode):
                The name of the model.

            model_sig (dict):
                The model's schema signature.

            stub (bool, optional):
                Whether this is a stub model. This is used internally to
                create models that only contain a primary key field and no
                others, for use when dealing with circular relationships.

            db_name (unicode, optional):
                The name of the database where the model would be read from or
                written to.
        """
        self.app_name = app_name
        self.model_name = model_name
        self._meta = MockMeta(proj_sig, app_name, model_name, model_sig)
        self._meta.setup_fields(self, stub)
        self._state = ModelState(db_name)

    def __repr__(self):
        """Return a string representation of the model.

        Returns:
            unicode:
            A string representation of the model.
        """
        return '<MockModel for %s.%s>' % (self.app_name, self.model_name)

    def __hash__(self):
        """Return a hash of the model instance.

        This is used to allow the model instance to be used as a key in a
        dictionary.

        Django would return a hash of the primary key's value, but that's not
        necessary for our needs, and we don't have field values in most mock
        models.

        Returns:
            int:
            The hash of the model.
        """
        return hash(id(self))

    def __eq__(self, other):
        """Return whether two mock models are equal.

        Both are considered equal if they're both mock models with the same
        app name and model name.

        Args:
            other (MockModel):
                The other mock model to compare to.

        Returns:
            bool:
            ``True`` if both are equal. ``False` if they are not.
        """
        # For our purposes, we don't want to appear equal to "self".
        # Really, Django 1.2 should be checking if this is a string before
        # doing this comparison,
        return (isinstance(other, MockModel) and
                self.app_name == other.app_name and
                self.model_name == other.model_name)


class MockRelated(object):
    """A mock RelatedObject for relation fields.

    This replicates some of the state and functionality of
    :py:class:`django.db.models.related.RelatedObject`, used for generating
    signatures and applying mutations.
    """

    def __init__(self, related_model, model, field):
        """Initialize the object.

        Args:
            related_model (MockModel):
                The mock model on the other end of the relation.

            model (MockModel):
                The mock model on this end of the relation.

            field (django.db.models.Field):
                The field owning the relation.
        """
        self.parent_model = related_model
        self.model = model
        self.opts = model._meta
        self.field = field
        self.name = '%s:%s' % (model.app_name, model.model_name)
        self.var_name = model.model_name.lower()

"""Utilities for building mock database models and fields."""

from __future__ import unicode_literals

from functools import partial

from django.db import models
from django.db.models.base import ModelState
from django.db.models.fields.related import RECURSIVE_RELATIONSHIP_CONSTANT

from django_evolution.compat import six
from django_evolution.compat.datastructures import OrderedDict
from django_evolution.compat.models import (FieldDoesNotExist,
                                            get_remote_field,
                                            get_remote_field_model)
from django_evolution.signature import FieldSignature, ModelSignature


def create_field(project_sig, field_name, field_type, field_attrs,
                 parent_model, related_model=None):
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

        related_model (unicode, optional):
            The full class path to a model this relates to. This requires
            a :py:class:`django.db.models.ForeignKey` field type.

    Returns:
        django.db.models.Field:
        A new field instance matching the provided data.
    """
    # Convert to the standard string format for each version of Python, to
    # simulate what the format would be for the default name.
    field_name = str(field_name)

    assert 'related_model' not in field_attrs, \
           ('related_model cannot be passed in field_attrs when calling '
            'create_field(). Pass the related_model parameter instead.')

    if related_model:
        related_app_name, related_model_name = related_model.split('.')
        related_model_sig = (
            project_sig
            .get_app_sig(related_app_name, required=True)
            .get_model_sig(related_model_name, required=True)
        )
        to = MockModel(project_sig=project_sig,
                       app_name=related_app_name,
                       model_name=related_model_name,
                       model_sig=related_model_sig,
                       stub=True)

        if (issubclass(field_type, models.ForeignKey) and
            hasattr(models, 'CASCADE') and
            'on_delete' not in field_attrs):
            # Starting in Django 2.0, on_delete is a requirement for
            # ForeignKeys. If not provided in the signature, we want to
            # default this to CASCADE, which is the value that Django
            # previously defaulted to.
            field_attrs = dict({
                'on_delete': models.CASCADE,
            }, **field_attrs)

        field = field_type(to, name=field_name, **field_attrs)
    else:
        field = field_type(name=field_name, **field_attrs)

    if (issubclass(field_type, models.ManyToManyField) and
        parent_model is not None):
        # Starting in Django 1.2, a ManyToManyField must have a through
        # model defined. This will be set internally to an auto-created
        # model if one isn't specified. We have to fake that model.
        through_model = field_attrs.get('through_model')
        through_model_sig = None

        if through_model:
            through_app_name, through_model_name = through_model.split('.')
            through_model_sig = (
                project_sig
                .get_app_sig(through_app_name)
                .get_model_sig(through_model_name)
            )
        elif hasattr(field, '_get_m2m_attr'):
            # Django >= 1.2
            remote_field = get_remote_field(field)
            remote_field_model = get_remote_field_model(remote_field)

            to_field_name = remote_field_model._meta.object_name.lower()

            if (remote_field_model == RECURSIVE_RELATIONSHIP_CONSTANT or
                to_field_name == parent_model._meta.object_name.lower()):
                from_field_name = 'from_%s' % to_field_name
                to_field_name = 'to_%s' % to_field_name
            else:
                from_field_name = parent_model._meta.object_name.lower()

            # This corresponds to the signature in
            # related.create_many_to_many_intermediary_model
            through_app_name = parent_model.app_name
            through_model_name = '%s_%s' % (parent_model._meta.object_name,
                                            field.name),

            through_model_sig = ModelSignature(
                model_name=through_model_name,
                table_name=field._get_m2m_db_table(parent_model._meta),
                pk_column='id',
                unique_together=[(from_field_name, to_field_name)])

            # 'id' field
            through_model_sig.add_field_sig(FieldSignature(
                field_name='id',
                field_type=models.AutoField,
                field_attrs={
                    'primary_key': True,
                }))

            # 'from' field
            through_model_sig.add_field_sig(FieldSignature(
                field_name=from_field_name,
                field_type=models.ForeignKey,
                field_attrs={
                    'related_name': '%s+' % through_model_name,
                },
                related_model='%s.%s' % (parent_model.app_name,
                                         parent_model._meta.object_name)))

            # 'to' field
            through_model_sig.add_field_sig(FieldSignature(
                field_name=to_field_name,
                field_type=models.ForeignKey,
                field_attrs={
                    'related_name': '%s+' % through_model_name,
                },
                related_model=related_model))

            field.auto_created = True

        if through_model_sig:
            through = MockModel(project_sig=project_sig,
                                app_name=through_app_name,
                                model_name=through_model_name,
                                model_sig=through_model_sig,
                                auto_created=not through_model,
                                managed=not through_model)
            get_remote_field(field).through = through

        field.m2m_db_table = partial(field._get_m2m_db_table,
                                     parent_model._meta)
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

    def __init__(self, project_sig, app_name, model_name, model_sig,
                 managed=False, auto_created=False):
        """Initialize the meta instance.

        Args:
            project_sig (django_evolution.signature.ProjectSignature):
                The project's schema signature.

            app_name (unicode):
                The name of the Django application owning the model.

            model_name (unicode):
                The name of the model.

            model_sig (dict):
                The model's schema signature.

            managed (bool, optional):
                Whether this represents a model managed internally by Django,
                rather than a developer-created model.

            auto_created (bool, optional):
                Whether this represents an auto-created model (such as an
                intermediary many-to-many model).
        """
        assert model_sig, \
            'model_sig for %s.%s cannot be None!' % (app_name, model_name)

        self.object_name = model_name
        self.app_label = app_name
        self.meta = {
            'auto_created': auto_created,
            'concrete_model': None,
            'constraints': [],
            'db_table': model_sig.table_name,
            'db_tablespace': model_sig.db_tablespace,
            'has_auto_field': None,
            'index_together': model_sig.index_together,
            'indexes': [],
            'managed': managed,
            'order_with_respect_to': None,
            'pk_column': model_sig.pk_column,
            'swapped': False,
            'unique_together': model_sig.unique_together,
        }

        if hasattr(models, 'Index'):
            self.meta['indexes'] = [
                models.Index(name=index_sig.name,
                             fields=index_sig.fields)
                for index_sig in model_sig.index_sigs
            ]

        self._fields = OrderedDict()
        self._many_to_many = OrderedDict()
        self.abstract = False
        self.managed = True
        self.proxy = False
        self._model_sig = model_sig
        self._project_sig = project_sig

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
        self.meta['model'] = model

        # Django 3.1 documents that the concrete class is the model at the
        # end of a proxy_for_model chain. In our case, it should always be
        # our mock model.
        self.meta['concrete_model'] = model

        for field_sig in self._model_sig.field_sigs:
            primary_key = field_sig.get_attr_value('primary_key')

            if not stub or primary_key:
                field = create_field(project_sig=self._project_sig,
                                     field_name=field_sig.field_name,
                                     field_type=field_sig.field_type,
                                     field_attrs=field_sig.field_attrs,
                                     parent_model=model,
                                     related_model=field_sig.related_model)

                if isinstance(field, models.AutoField):
                    self.meta['has_auto_field'] = True
                    self.meta['auto_field'] = field

                if isinstance(field, models.ManyToManyField):
                    self._many_to_many[field.name] = field
                else:
                    self._fields[field.name] = field

                field.set_attributes_from_name(field.name)

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

    def __init__(self, project_sig, app_name, model_name, model_sig,
                 auto_created=False, managed=False, stub=False, db_name=None):
        """Initialize the model.

        Args:
            project_sig (django_evolution.signature.ProjectSignature):
                The project's schema signature.

            app_name (unicode):
                The name of the Django app that owns the model.

            model_name (unicode):
                The name of the model.

            model_sig (dict):
                The model's schema signature.

            auto_created (bool, optional):
                Whether this represents an auto-created model (such as an
                intermediary many-to-many model).

            managed (bool, optional):
                Whether this represents a model managed internally by Django,
                rather than a developer-created model.

            stub (bool, optional):
                Whether this is a stub model. This is used internally to
                create models that only contain a primary key field and no
                others, for use when dealing with circular relationships.

            db_name (unicode, optional):
                The name of the database where the model would be read from or
                written to.
        """
        assert model_sig, \
            'model_sig for %s.%s cannot be None!' % (app_name, model_name)

        self.app_name = app_name
        self.model_name = model_name
        self._meta = MockMeta(project_sig=project_sig,
                              app_name=app_name,
                              model_name=model_name,
                              model_sig=model_sig,
                              auto_created=auto_created,
                              managed=managed)
        self._meta.setup_fields(self, stub)

        self._state = ModelState()
        self._state.db = db_name

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
            ``True`` if both are equal. ``False`` if they are not.
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

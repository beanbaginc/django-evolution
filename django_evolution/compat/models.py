"""Compatibility functions for model-related operations.

This provides functions for working with models or importing moved fields.
These translate to the various versions of Django that are supported.
"""

from __future__ import unicode_literals

from django.db import models
from django.db.models.fields import related

try:
    # Django >= 1.7
    from django.apps.registry import apps
    from django.contrib.contenttypes.fields import (GenericForeignKey,
                                                    GenericRelation)

    cache = None
    all_models = apps.all_models
    get_model = apps.get_model
    _get_models = None
except ImportError:
    # Django < 1.7
    from django.db.models.loading import (cache, get_model,
                                          get_models as _get_models)
    from django.contrib.contenttypes.generic import (GenericForeignKey,
                                                     GenericRelation)

    all_models = cache.app_models
    apps = None

try:
    # Django >= 1.8
    from django.core.exceptions import FieldDoesNotExist
except ImportError:
    # Django < 1.8
    from django.db.models.fields import FieldDoesNotExist


def get_models(app_mod=None, include_auto_created=False):
    """Return the models belonging to an app.

    Args:
        app_mod (module, optional):
            The application module.

        include_auto_created (bool, optional):
            Whether to return auto-created models (such as many-to-many
            models) in the results.

    Returns:
        list:
        The list of modules belonging to the app.
    """
    if apps:
        # Django >= 1.7
        if app_mod is None:
            return apps.get_models(include_auto_created=include_auto_created)

        for app_config in apps.get_app_configs():
            if app_config.models_module is app_mod:
                return [
                    model
                    for model in app_config.get_models(
                        include_auto_created=include_auto_created)
                    if not model._meta.abstract
                ]

        return []
    else:
        # Django < 1.7
        models = _get_models(app_mod,
                             include_auto_created=include_auto_created)

        if app_mod is not None:
            # Avoids a circular import.
            from django_evolution.utils.apps import get_app_name

            app_mod_name = get_app_name(app_mod)

            models = [
                model
                for model in models
                if model.__module__.startswith(app_mod_name)
            ]

        return models


def set_model_name(model, name):
    """Set the name of a model.

    Args:
        model (django.db.models.Model):
            The model to set the new name on.

        name (str):
            The new model name.
    """
    if hasattr(model._meta, 'model_name'):
        # Django >= 1.7
        model._meta.model_name = name
    else:
        # Django < 1.7
        model._meta.module_name = name


def get_model_name(model):
    """Return the model's name.

    Args:
        model (django.db.models.Model):
            The model for which to return the name.

    Returns:
        str: The model's name.
    """
    if hasattr(model._meta, 'model_name'):
        # Django >= 1.7
        return model._meta.model_name
    else:
        # Django < 1.7
        return model._meta.module_name


def get_field_is_hidden(field):
    """Return whether a field is hidden.

    Version Added:
        2.2

    Args:
        field (django.db.models.Field):
            The field to check.

    Returns:
        bool:
        ``True`` if the field is hidden. ``False`` if it is not.
    """
    if hasattr(field, 'hidden'):
        # Django >= 1.8
        return field.hidden
    else:
        # Django < 1.8
        if hasattr(field, 'rel'):
            return field.rel.is_hidden()
        else:
            return field.is_hidden()


def get_field_is_many_to_many(field):
    """Return whether a field is a Many-to-Many field.

    Version Added:
        2.2

    Args:
        field (django.db.models.Field):
            The field to check.

    Returns:
        bool:
        ``True`` if the field is a Many-to-Many field. ``False`` if it is not.
    """
    if hasattr(field, 'many_to_many'):
        # Django >= 1.8
        return field.many_to_many
    else:
        # Django < 1.8
        return isinstance(field, (models.ManyToManyField,
                                  related.ManyToManyRel))


def get_field_is_relation(field):
    """Return whether a field is a relation.

    A field is a relation if it's an object like a
    :py:class:`django.db.models.ForeignKey` or
    :py:class:`django.db.models.ManyToManyField`, or if it's a relation
    utility field like
    :py:class:`django.db.models.fields.related.ForeignObjectRel` or
    :py:class:`django.db.models.fields.related.ManyToOneRel`.

    Version Added:
        2.2

    Args:
        field (django.db.models.Field or
               django.db.models.fields.related.ForeignObjectRel):
            The field to check.

    Returns:
        bool:
        ``True`` if the field is a relation. ``False`` if it is not.
    """
    if hasattr(field, 'is_relation'):
        # Django >= 1.8
        return field.is_relation
    else:
        # Django < 1.8
        return (getattr(field, 'rel', None) is not None or
                isinstance(field, (related.ForeignObjectRel,
                                   related.ManyToManyRel)))


def get_rel_target_field(field):
    """Return the target field for a field's relation.

    Warning:
        Despite the name, this should only be called on a
        :py:class:`ForeignKey` and not on a relation, in order to avoid
        consistency issues in the data returned on Django >= 1.7.

    Args:
        field (django.db.models.Field):
            The relation field.

    Returns:
        django.db.models.Field:
        The field on the other end of the relation.
    """
    if hasattr(field, 'target_field'):
        # Django >= 1.7
        return field.target_field
    else:
        # Django < 1.7
        return field.related_field


def get_remote_field(field):
    """Return the remote field for a relation.

    This will be an intermediary field, such as:

    * :py:class:`django.db.models.fields.related.ForeignObjectRel`
    * :py:class:`django.db.models.fields.related.ManyToOneRel`
    * :py:class:`django.db.models.fields.related.OneToOneRel`
    * :py:class:`django.db.models.fields.related.ManyToManyRel`

    This is equivalent to ``rel`` prior to Django 1.9 and ``remote_field``
    in 1.9 onward.

    Version Changed:
        2.2:
        On Django < 1.9, a main relation field (like
        :py:class:`django.db.models.ForeignKey`) will return the utility
        relation, matching the behavior on >= 1.9.

    Args:
        field (django.db.models.Field):
            The relation field.

    Returns:
        django.db.models.Field:
        The remote field on the relation.
    """
    if hasattr(field, 'remote_field'):
        # Django >= 1.9
        return field.remote_field
    else:
        # Django < 1.9
        if hasattr(field, 'rel'):
            return field.rel
        elif isinstance(field, related.ManyToManyRel):
            return getattr(field.to, field.related_name).related.field
        elif isinstance(field, related.ForeignObjectRel):
            return field.field

        raise NotImplementedError('Unsupported field/relation type: %r'
                                  % field)


def get_remote_field_model(rel):
    """Return the model a relation is pointing to.

    This is equivalent to ``rel.to`` prior to Django 1.9 and
    ``remote_field.model`` in 1.9 onward.

    Args:
        rel (object):
            The relation object. This is expected to be the result of a
            :py:func:`get_remote_field` call.

    Returns:
        type:
        The model the relation points to. This should be a subclass of
        :py:meth:`django.db.models.Model`.
    """
    if hasattr(rel, 'model'):
        # Django >= 1.9
        return rel.model
    else:
        # Django < 1.9
        return rel.to


def get_remote_field_related_model(rel):
    """Return the model a relation is pointing from.

    Version Added:
        2.2

    Args:
        rel (object):
            The relation object. This is expected to be the result of a
            :py:func:`get_remote_field` call.

    Returns:
        type:
        The model the relation points to. This should be a subclass of
        :py:meth:`django.db.models.Model`.
    """
    if hasattr(rel, 'related_model'):
        # Django >= 1.9
        return rel.related_model
    else:
        # Django < 1.9
        if isinstance(rel, models.ForeignKey):
            return rel.rel.get_related_field().model
        elif isinstance(rel, models.ManyToManyField):
            return rel.rel.to
        elif isinstance(rel, related.ManyToOneRel):
            return rel.field.model
        elif isinstance(rel, related.ManyToManyRel):
            return getattr(rel.to, rel.related_name).related.model
        elif isinstance(rel, related.ForeignObjectRel):
            return rel.get_related_field().model

        raise NotImplementedError('Unsupported field/relation type: %r' % rel)


__all__ = [
    'FieldDoesNotExist',
    'GenericForeignKey',
    'GenericRelation',
    'all_models',
    'get_field_is_hidden',
    'get_field_is_many_to_many',
    'get_field_is_relation',
    'get_model',
    'get_models',
    'get_model_name',
    'get_rel_target_field',
    'get_remote_field',
    'get_remote_field_model',
    'get_remote_field_related_model',
    'set_model_name',
]

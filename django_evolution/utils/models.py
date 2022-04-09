"""Utilities for working with models."""

from __future__ import unicode_literals

from collections import defaultdict

from django.db import router

from django_evolution.compat import six
from django_evolution.compat.models import (get_field_is_hidden,
                                            get_field_is_many_to_many,
                                            get_field_is_relation,
                                            get_model,
                                            get_models,
                                            get_remote_field,
                                            get_remote_field_model,
                                            get_remote_field_related_model)


_rel_tree_cache = None


def get_database_for_model_name(app_name, model_name):
    """Return the database used for a given model.

    Given an app name and a model name, this will return the proper
    database connection name used for making changes to that model. It
    will go through any custom routers that understand that type of model.

    Args:
        app_name (unicode):
            The name of the app owning the model.

        model_name (unicode):
            The name of the model.

    Returns:
        unicode:
        The name of the database used for the model.
    """
    return router.db_for_write(get_model(app_name, model_name))


def walk_model_tree(model):
    """Walk through a tree of models.

    This will yield the provided model and its parents, in turn yielding
    their parents, and so on.

    Version Added:
        2.2

    Args:
        model (type):
            The top of the model tree to iterate through.

    Yields:
        type:
        Each model class in the tree.
    """
    yield model

    for parent in model._meta.parents:
        for _model in walk_model_tree(parent):
            yield _model


def get_model_rel_tree():
    """Return the full field relationship tree for all registered models.

    This will walk through every field in every model registered in Django,
    storing the relationships between objects, caching them. Each entry in
    the resulting dictionary will be a table mapping to a list of relation
    fields that point back at it.

    This can be used to quickly locate any and all reverse relations made to
    a field.

    This is similar to Django's built-in reverse relation tree used internally
    (with different implementations) in
    :py:class:`django.db.models.options.Options`, but works across all
    supported versions of Django, and supports cache clearing.

    Version Added:
        2.2

    Returns:
        dict:
        The model relation tree.
    """
    global _rel_tree_cache

    if _rel_tree_cache is not None:
        return _rel_tree_cache

    rel_tree = defaultdict(list)
    all_models = get_models(include_auto_created=True)

    # We'll walk the entire model tree, looking for any immediate fields on
    # each model, building a mapping of models to fields that reference the
    # model.
    for cur_model in all_models:
        if cur_model._meta.abstract:
            continue

        for field in iter_model_fields(cur_model,
                                       include_parent_models=False,
                                       include_forward_fields=True,
                                       include_reverse_fields=False,
                                       include_hidden_fields=False):
            if (get_field_is_relation(field) and
                get_remote_field_related_model(field) is not None):
                remote_field = get_remote_field(field)
                remote_field_model = get_remote_field_model(remote_field)

                # Make sure this isn't a "self" relation or similar.
                if not isinstance(remote_field_model, six.string_types):
                    db_table = \
                        remote_field_model._meta.concrete_model._meta.db_table
                    rel_tree[db_table].append(field)

    _rel_tree_cache = rel_tree

    return rel_tree


def clear_model_rel_tree():
    """Clear the model relationship tree.

    This will cause the next call to :py:func:`get_model_rel_tree` to
    re-compute the full tree.

    Version Added:
        2.2
    """
    global _rel_tree_cache

    _rel_tree_cache = None


def iter_model_fields(model,
                      include_parent_models=True,
                      include_forward_fields=True,
                      include_reverse_fields=False,
                      include_hidden_fields=False,
                      seen_models=None):
    """Iterate through all fields on a model using the given criteria.

    This is roughly equivalent to Django's internal
    :py:func:`django.db.models.options.Option._get_fields` on Django 1.8+,
    but makes use of our model reverse relation tree, and works across all
    supported versions of Django.

    Version Added:
        2.2

    Args:
        model (type):
            The model owning the fields.

        include_parent_models (bool, optional):
            Whether to include fields defined on parent models.

        include_forward_fields (bool, optional):
            Whether to include fields owned by the model (or a parent).

        include_reverse_fields (bool, optional):
            Whether to include fields on other models that point to this
            model.

        include_hidden_fields (bool, optional):
            Whether to include hidden fields.

        seen_models (set, optional):
            Models seen during iteration. This is intended for internal
            use only by this function.

    Yields:
        django.db.models.Field:
        Each field matching the criteria.
    """
    concrete_model = model._meta.concrete_model

    if seen_models is None:
        seen_models = set()

    if include_parent_models:
        candidate_models = walk_model_tree(model)
    else:
        candidate_models = [model]

    if include_reverse_fields:
        # Find all models containing fields that point to this model.
        rel_tree = get_model_rel_tree()
        rel_fields = rel_tree.get(model._meta.concrete_model._meta.db_table,
                                  [])
    else:
        rel_fields = []

    for cur_model in candidate_models:
        cur_model_label = cur_model._meta.db_table

        if (cur_model_label in seen_models or
            cur_model._meta.concrete_model != concrete_model):
            continue

        seen_models.add(cur_model_label)

        if include_parent_models:
            for parent in cur_model._meta.parents:
                if parent not in seen_models:
                    parent_fields = iter_model_fields(
                        parent,
                        include_parent_models=True,
                        include_forward_fields=include_forward_fields,
                        include_reverse_fields=include_reverse_fields,
                        include_hidden_fields=include_hidden_fields)

                    for field in parent_fields:
                        yield field

        if include_reverse_fields and not cur_model._meta.proxy:
            for rel_field in rel_fields:
                remote_field = get_remote_field(rel_field)

                if (include_hidden_fields or
                    not get_field_is_hidden(remote_field)):
                    yield remote_field

        if include_forward_fields:
            for field in cur_model._meta.local_fields:
                yield field

            for field in cur_model._meta.local_many_to_many:
                yield field

    # Django >= 1.10
    for field in getattr(model._meta, 'private_fields', []):
        yield field


def iter_non_m2m_reverse_relations(field):
    """Iterate through non-M2M reverse relations pointing to a field.

    This will exclude any :py:class:`~django.db.models.ManyToManyField`s,
    but will include the relation fields on their "through" tables.

    Note that this may return duplicate results, or multiple relations
    pointing to the same field. It's up to the caller to handle this.

    Version Added:
        2.2

    Args:
        field (django.db.models.Field):
            The field that relations must point to.

    Yields:
        django.db.models.Field or object:
        Each field or relation object pointing to this field.

        The type of the relation object depends on the version of Django.
    """
    is_primary_key = field.primary_key
    field_name = field.name

    for rel in iter_model_fields(field.model,
                                 include_parent_models=True,
                                 include_forward_fields=False,
                                 include_reverse_fields=True,
                                 include_hidden_fields=True):
        rel_from_field = rel.field

        # Exclude any ManyToManyFields, and make sure the referencing fields
        # point directly to the ID on this field.
        if (not get_field_is_many_to_many(rel_from_field) and
            ((is_primary_key and rel_from_field.to_fields == [None]) or
             field_name in rel_from_field.to_fields)):
            yield rel

            # Now do the same for the fields on the model of the related field.
            other_rel_fields = iter_non_m2m_reverse_relations(
                get_remote_field(rel))

            for rel2 in other_rel_fields:
                yield rel2

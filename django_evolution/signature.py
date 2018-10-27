from __future__ import unicode_literals

from django.conf import global_settings
from django.db.models.fields.related import ForeignKey
from django.utils import six

from django_evolution.compat.apps import get_apps
from django_evolution.compat.datastructures import OrderedDict
from django_evolution.compat.db import (db_router_allows_migrate,
                                        db_router_allows_syncdb)
from django_evolution.compat.models import (GenericRelation, get_models,
                                            get_remote_field_model)
from django_evolution.db import EvolutionOperationsMulti
from django_evolution.utils import get_app_label


ATTRIBUTE_DEFAULTS = {
    # Common to all fields
    'primary_key': False,
    'max_length': None,
    'unique': False,
    'null': False,
    'db_index': False,
    'db_column': None,
    'db_tablespace': global_settings.DEFAULT_TABLESPACE,
    'rel': None,
    # Decimal Field
    'max_digits': None,
    'decimal_places': None,
    # ManyToManyField
    'db_table': None
}

ATTRIBUTE_ALIASES = {
    # r7790 modified the unique attribute of the meta model to be
    # a property that combined an underlying _unique attribute with
    # the primary key attribute. We need the underlying property,
    # but we don't want to affect old signatures (plus the
    # underscore is ugly :-).
    'unique': '_unique',

    # Django 1.9 moved from 'rel' to 'remote_field' for relations, but
    # for compatibility reasons we want to retain 'rel' in our signatures.
    'rel': 'remote_field',
}


def create_field_sig(field):
    field_sig = OrderedDict()
    field_sig['field_type'] = field.__class__

    for attrib in six.iterkeys(ATTRIBUTE_DEFAULTS):
        alias = ATTRIBUTE_ALIASES.get(attrib)

        if alias and hasattr(field, alias):
            value = getattr(field, alias)
        elif hasattr(field, attrib):
            value = getattr(field, attrib)
        else:
            continue

        if isinstance(field, ForeignKey) and attrib == 'db_index':
            default = True
        else:
            default = ATTRIBUTE_DEFAULTS[attrib]

        # only store non-default values
        if default != value:
            field_sig[attrib] = value

    rel = field_sig.pop('rel', None)

    if rel:
        related_model = get_remote_field_model(rel)
        field_sig['related_model'] = str('%s.%s' % (
            related_model._meta.app_label,
            related_model._meta.object_name))

    return field_sig


def create_model_sig(model):
    fields = OrderedDict()

    model_sig = {
        'meta': {
            'unique_together': model._meta.unique_together,
            'index_together': getattr(model._meta, 'index_together', []),
            'db_tablespace': model._meta.db_tablespace,
            'db_table': model._meta.db_table,
            'pk_column': str(model._meta.pk.column),
            '__unique_together_applied': True,
        },
        'fields': fields,
    }

    if getattr(model._meta, 'indexes', None):
        indexes_sig = []

        for index in model._meta.original_attrs['indexes']:
            index_sig = {
                'fields': index.fields,
            }

            if index.name:
                index_sig['name'] = index.name

            indexes_sig.append(index_sig)

        model_sig['meta']['indexes'] = indexes_sig

    for field in model._meta.local_fields + model._meta.local_many_to_many:
        # Special case - don't generate a signature for generic relations
        if not isinstance(field, GenericRelation):
            fields[str(field.name)] = create_field_sig(field)

    return model_sig


def create_app_sig(app, database):
    """
    Creates a dictionary representation of the models in a given app.
    Only those attributes that are interesting from a schema-evolution
    perspective are included.
    """
    app_sig = OrderedDict()

    for model in get_models(app):
        # Only include those models that can be synced.
        #
        # On Django 1.7 and up, we need to check if the model allows for
        # migrations (using Router.allow_migrate).
        #
        # On older versions of Django, we check if the model allows for
        # synchronization to the database (Router.allow_syncdb).
        if (db_router_allows_migrate(database, get_app_label(app), model) or
            db_router_allows_syncdb(database, model)):
            app_sig[model._meta.object_name] = create_model_sig(model)

    return app_sig


def create_project_sig(database):
    """
    Create a dictionary representation of the apps in a given project.
    """
    proj_sig = {
        '__version__': 1,
    }

    for app in get_apps():
        proj_sig[get_app_label(app)] = create_app_sig(app, database)

    return proj_sig


def has_indexes_changed(old_model_sig, new_model_sig):
    """Return whether indexes have changed between signatures.

    Args:
        old_model_sig (dict):
            Old signature for the model.

        new_model_sig (dict):
            New signature for the model.

    Returns:
        bool:
        ```True``` if there are any differences in indexes.
    """
    return (old_model_sig['meta'].get('indexes', []) !=
            new_model_sig['meta'].get('indexes', []))


def has_index_together_changed(old_model_sig, new_model_sig):
    """Returns whether index_together has changed between signatures."""
    old_meta = old_model_sig['meta']
    new_meta = new_model_sig['meta']
    old_index_together = old_meta.get('index_together', [])
    new_index_together = new_meta['index_together']

    return list(old_index_together) != list(new_index_together)


def has_unique_together_changed(old_model_sig, new_model_sig):
    """Returns whether unique_together has changed between signatures.

    unique_together is considered to have changed under the following
    conditions:

        * They are different in value.
        * Either the old or new is non-empty (even if equal) and evolving
          from an older signature from Django Evolution pre-0.7, where
          unique_together wasn't applied to the database.
    """
    old_meta = old_model_sig['meta']
    new_meta = new_model_sig['meta']
    old_unique_together = old_meta['unique_together']
    new_unique_together = new_meta['unique_together']

    return (list(old_unique_together) != list(new_unique_together) or
            ((old_unique_together or new_unique_together) and
             not old_meta.get('__unique_together_applied', False)))


def record_unique_together_applied(model_sig):
    """Records that unique_together was applied.

    This will prevent that unique_together from becoming invalidated in
    future evolutions.
    """
    model_sig['meta']['__unique_together_applied'] = True

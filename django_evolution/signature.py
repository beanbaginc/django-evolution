from django.db import connections
from django.db.models import get_apps, get_models
from django.db.models.fields.related import ForeignKey
from django.conf import global_settings
from django.contrib.contenttypes import generic
from django.utils.datastructures import SortedDict

from django_evolution import is_multi_db
from django_evolution.db import EvolutionOperationsMulti

if is_multi_db():
    from django.db import router


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

# r7790 modified the unique attribute of the meta model to be
# a property that combined an underlying _unique attribute with
# the primary key attribute. We need the underlying property,
# but we don't want to affect old signatures (plus the
# underscore is ugly :-).
ATTRIBUTE_ALIASES = {
    'unique': '_unique'
}


def create_field_sig(field):
    field_sig = {
        'field_type': field.__class__,
    }

    for attrib in ATTRIBUTE_DEFAULTS.keys():
        alias = ATTRIBUTE_ALIASES.get(attrib, attrib)

        if hasattr(field, alias):
            value = getattr(field, alias)

            if isinstance(field, ForeignKey):
                if attrib == 'db_index':
                    default = True
                else:
                    default = ATTRIBUTE_DEFAULTS[attrib]
            else:
                default = ATTRIBUTE_DEFAULTS[attrib]

            # only store non-default values
            if default != value:
                field_sig[attrib] = value

    rel = field_sig.pop('rel', None)

    if rel:
        field_sig['related_model'] = str('.'.join([rel.to._meta.app_label,
                                                   rel.to._meta.object_name]))

    return field_sig


def create_model_sig(model):
    model_sig = {
        'meta': {
            'unique_together': model._meta.unique_together,
            'db_tablespace': model._meta.db_tablespace,
            'db_table': model._meta.db_table,
            'pk_column': str(model._meta.pk.column),
        },
        'fields': {},
    }

    for field in model._meta.local_fields + model._meta.local_many_to_many:
        # Special case - don't generate a signature for generic relations
        if not isinstance(field, generic.GenericRelation):
            model_sig['fields'][str(field.name)] = create_field_sig(field)

    return model_sig


def create_app_sig(app, database):
    """
    Creates a dictionary representation of the models in a given app.
    Only those attributes that are interesting from a schema-evolution
    perspective are included.
    """
    app_sig = SortedDict()

    for model in get_models(app):
        # only include those who want to be syncdb
        if not is_multi_db() or router.allow_syncdb(database, model):
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
        proj_sig[app.__name__.split('.')[-2]] = create_app_sig(app, database)

    return proj_sig


def create_empty_database_table_sig():
    """Creates an empty table signature for the database signature.

    This represents a completely blank entry, with just the necessary
    defaults. It is meant to be filled in by the caller.
    """
    return {
        'indexes': {},
    }


def create_database_sig(database):
    """Creates a dictionary representing useful state in the database.

    This signature is used only during evolution/simulation. It is not
    stored.
    """
    database_sig = {}

    rescan_indexes_for_database_sig(database_sig, database)

    return database_sig


def rescan_indexes_for_database_sig(database_sig, database):
    evolver = EvolutionOperationsMulti(database).get_evolver()
    connection = evolver.connection
    introspection = connection.introspection
    cursor = connection.cursor()

    for table_name in introspection.get_table_list(cursor):
        table_sig = create_empty_database_table_sig()
        indexes = evolver.get_indexes_for_table(table_name)

        for index_name, index_info in indexes.iteritems():
            table_sig['indexes'][index_name] = index_info

        database_sig[table_name] = table_sig


def add_index_to_database_sig(evolver, database_sig, model, fields,
                              index_name, unique=False):
    """Adds an index to the database signature.

    This index can be used for later lookup during the evolution process.
    It won't otherwise be preserved, though the resulting indexes are
    expected to match the result in the database.
    """
    table_name = model._meta.db_table
    assert table_name in database_sig

    database_sig[table_name]['indexes'][index_name] = {
        'unique': unique,
        'columns': [field.column for field in fields],
    }


def remove_index_from_database_sig(database_sig, model, index_name,
                                   unique=False):
    """Removes an index from the database signature.

    This index will no longer be found during lookups when generating
    evolution SQL, even if it exists in the database.
    """
    table_name = model._meta.db_table
    assert table_name in database_sig

    indexes = database_sig[table_name]['indexes']
    assert index_name in indexes
    assert unique == indexes[index_name]['unique']

    del indexes[index_name]

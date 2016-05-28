import copy
import logging
from datetime import datetime
from functools import partial

import django
from django.conf import settings
from django.db import connection, connections, models
from django.db.utils import DEFAULT_DB_ALIAS

from django_evolution import signature
from django_evolution.compat.apps import (is_app_registered, register_app,
                                          register_app_models,
                                          unregister_app,
                                          unregister_app_model)
from django_evolution.compat.datastructures import OrderedDict
from django_evolution.compat.db import (atomic,
                                        create_index_name,
                                        digest,
                                        sql_create, sql_delete,
                                        truncate_name)
from django_evolution.compat.models import (all_models, get_models,
                                            get_model_name, set_model_name)
from django_evolution.db import EvolutionOperationsMulti
from django_evolution.signature import rescan_indexes_for_database_sig
from django_evolution.tests import models as evo_test
from django_evolution.utils import write_sql, execute_sql


DEFAULT_TEST_ATTRIBUTE_VALUES = {
    models.CharField: 'TestCharField',
    models.IntegerField: '123',
    models.AutoField: None,
    models.DateTimeField: datetime.now(),
    models.PositiveIntegerField: '42'
}


def _register_models(database_sig, app_label='tests', db_name='default',
                     app=evo_test, *models, **kwargs):
    """Register models for testing purposes.

    Args:
        database_sig (dict):
            The database signature to populate with model information.

        app_label (str, optional):
            The label for the test app. Defaults to "tests".

        db_name (str, optional):
            The name of the database connection. Defaults to "default".

        app (module, optional):
            The application module for the test models.

        *models (tuple):
            The models to register.

        **kwargs (dict):
            Additional keyword arguments. This supports:

            ``register_indexes``:
                Specifies whether indexes should be registered for any
                models. Defaults to ``False``.

    Returns:
        collections.OrderedDict:
        A dictionary of registered models. The keys are model names, and
        the values are the models.
    """
    django_evolution_models = all_models['django_evolution']

    app_cache = OrderedDict()
    evolver = EvolutionOperationsMulti(db_name, database_sig).get_evolver()
    register_indexes = kwargs.get('register_indexes', False)

    my_connection = connections[db_name or DEFAULT_DB_ALIAS]
    max_name_length = my_connection.ops.max_name_length()

    for name, model in reversed(models):
        orig_model_name = get_model_name(model)

        if orig_model_name in django_evolution_models:
            unregister_app_model('django_evolution', orig_model_name)

        orig_db_table = model._meta.db_table
        orig_object_name = model._meta.object_name

        generated_db_table = truncate_name(
            '%s_%s' % (model._meta.app_label, orig_model_name),
            max_name_length)

        if orig_db_table.startswith(generated_db_table):
            model._meta.db_table = '%s_%s' % (app_label, name.lower())

        model._meta.db_table = truncate_name(model._meta.db_table,
                                             max_name_length)
        model._meta.app_label = app_label
        model._meta.object_name = name
        model_name = name.lower()
        set_model_name(model, model_name)

        # Add an entry for the table in database_sig, if it's not already
        # there.
        if model._meta.db_table not in database_sig:
            database_sig[model._meta.db_table] = \
                signature.create_empty_database_table_sig()

        if register_indexes:
            # Now that we definitely have an entry, store the indexes for
            # all the fields in database_sig, so that other operations can
            # look up the index names.
            for field in model._meta.local_fields:
                if field.db_index or field.unique:
                    index_name = create_index_name(
                        my_connection,
                        model._meta.db_table,
                        field_names=[field.name],
                        col_names=[field.column],
                        unique=field.unique)

                    signature.add_index_to_database_sig(
                        evolver, database_sig, model, [field],
                        index_name=index_name,
                        unique=field.unique)

            for field_names in model._meta.unique_together:
                index_name = create_index_name(
                    my_connection,
                    model._meta.db_table,
                    field_names=field_names,
                    unique=True)

                signature.add_index_to_database_sig(
                    evolver, database_sig, model,
                    evolver.get_fields_for_names(model, field_names),
                    index_name=index_name,
                    unique=True)

            for field_names in getattr(model._meta, 'index_together', []):
                fields = evolver.get_fields_for_names(model, field_names)
                index_name = create_index_name(
                    my_connection,
                    model._meta.db_table,
                    field_names=[field.name for field in fields],
                    col_names=[field.column for field in fields])

                signature.add_index_to_database_sig(
                    evolver, database_sig, model,
                    fields,
                    index_name=index_name)

        # Register the model with the app.
        add_app_test_model(model, app_label=app_label)

        for field in model._meta.local_many_to_many:
            if not field.rel.through:
                continue

            through = field.rel.through

            generated_db_table = truncate_name(
                '%s_%s' % (orig_db_table, field.name),
                max_name_length)

            if through._meta.db_table == generated_db_table:
                through._meta.app_label = app_label

                # Transform the 'through' table information only
                # if we've transformed the parent db_table.
                if model._meta.db_table != orig_db_table:
                    through._meta.db_table = \
                        '%s_%s' % (model._meta.db_table, field.name)

                    through._meta.object_name = \
                        through._meta.object_name.replace(
                            orig_object_name,
                            model._meta.object_name)

                    set_model_name(
                        through,
                        get_model_name(through).replace(orig_model_name,
                                                        model_name))

            through._meta.db_table = \
                truncate_name(through._meta.db_table, max_name_length)

            for field in through._meta.local_fields:
                if field.rel and field.rel.to:
                    column = field.column

                    if (column.startswith(orig_model_name) or
                        column.startswith('to_%s' % orig_model_name) or
                        column.startswith('from_%s' % orig_model_name)):

                        field.column = column.replace(
                            orig_model_name,
                            get_model_name(model))

            through_model_name = get_model_name(through)

            if through_model_name in django_evolution_models:
                unregister_app_model('django_evolution', through_model_name)

            app_cache[through_model_name] = through
            add_app_test_model(through, app_label=app_label)

        app_cache[model_name] = model

    if not is_app_registered(app):
        register_app(app_label, app)

    return app_cache


def register_models(database_sig, *models, **kwargs):
    return _register_models(database_sig, 'tests', 'default', evo_test,
                            *models, **kwargs)


def register_models_multi(database_sig, app_label, db_name, *models, **kwargs):
    return _register_models(database_sig, app_label, db_name, evo_test,
                            *models, **kwargs)


def _test_proj_sig(app_label, *models, **kwargs):
    "Generate a dummy project signature based around a single model"
    version = kwargs.get('version', 1)
    proj_sig = {
        app_label: OrderedDict(),
        '__version__': version,
    }

    # Compute the project siguature
    for full_name, model in models:
        parts = full_name.split('.')

        if len(parts) == 1:
            name = parts[0]
            app = app_label
        else:
            app, name = parts

        proj_sig.setdefault(app, OrderedDict())[name] = \
            signature.create_model_sig(model)

    return proj_sig


def create_test_proj_sig(*models, **kwargs):
    return _test_proj_sig('tests', *models, **kwargs)


def create_test_proj_sig_multi(app_label, *models, **kwargs):
    return _test_proj_sig(app_label, *models, **kwargs)

# XXX Legacy names for these functions
test_proj_sig = create_test_proj_sig
test_proj_sig_multi = create_test_proj_sig_multi


def execute_transaction(sql, output=False, database='default'):
    "A transaction wrapper for executing a list of SQL statements"
    my_connection = connection
    out_sql = []

    if not database:
        database = DEFAULT_DB_ALIAS

    my_connection = connections[database]

    try:
        with atomic(using=database):
            cursor = my_connection.cursor()

            # Perform the SQL
            if output:
                out_sql.extend(write_sql(sql, database))

            execute_sql(cursor, sql, database)
    except Exception, e:
        logging.error('Error executing SQL %s: %s' % (sql, e))
        raise

    return out_sql


def execute_test_sql(start, end, sql, debug=False, app_label='tests',
                     database='default', database_sig=None, return_sql=False,
                     rescan_indexes=True):
    """
    Execute a test SQL sequence. This method also creates and destroys the
    database tables required by the models registered against the test
    application.

    start and end are the start- and end-point states of the application cache.

    sql is the list of sql statements to execute.

    cleanup is a list of extra sql statements required to clean up. This is
    primarily for any extra m2m tables that were added during a test that won't
    be cleaned up by Django's sql_delete() implementation.

    debug is a helper flag. It displays the ALL the SQL that would be executed,
    (including setup and teardown SQL), and executes the Django-derived
    setup/teardown SQL.
    """
    out_sql = []

    # Set up the initial state of the app cache
    set_app_test_models(copy.deepcopy(start), app_label=app_label)

    # Install the initial tables and indicies
    execute_transaction(sql_create(evo_test, database),
                        output=debug, database=database)

    if rescan_indexes and database_sig:
        rescan_indexes_for_database_sig(database_sig, database)

    create_test_data(get_models(evo_test), database)

    # Set the app cache to the end state
    set_app_test_models(copy.deepcopy(end), app_label=app_label)

    try:
        if callable(sql):
            sql = sql()

        # Execute the test sql
        if debug:
            out_sql.extend(write_sql(sql, database))
        else:
            out_sql.extend(execute_transaction(sql, output=True,
                                               database=database))
    finally:
        # Cleanup the apps.
        delete_sql = sql_delete(evo_test, database)

        if debug:
            out_sql.append(delete_sql)
        else:
            out_sql.extend(execute_transaction(delete_sql, output=False,
                                               database=database))

    # This is a terrible hack, but it's necessary while we use doctests
    # and normal unit tests. If we always return the SQL, then the
    # doctests will expect us to compare the output of that (along with the
    # print statements).
    #
    # Down the road, everything should be redone to be standard unit tests,
    # and then we can just compare the returned SQL statements instead of
    # dealing with anything on stdout.
    if return_sql:
        return out_sql
    else:
        return None


def create_test_data(app_models, database):
    deferred_models = []
    deferred_fields = {}
    using_args = {
        'using': database,
    }

    for model in app_models:
        params = {}
        deferred = False

        for field in model._meta.fields:
            if not deferred:
                if type(field) in (models.ForeignKey, models.ManyToManyField):
                    related_model = field.rel.to
                    related_q = related_model.objects.all().using(database)

                    if related_q.count():
                        related_instance = related_q[0]
                    elif field.null is False:
                        # Field cannot be null yet the related object
                        # hasn't been created yet Defer the creation of
                        # this model
                        deferred = True
                        deferred_models.append(model)
                    else:
                        # Field cannot be set yet but null is acceptable
                        # for the moment
                        deferred_fields[type(model)] = \
                            deferred_fields.get(type(model),
                                                []).append(field)
                        related_instance = None

                    if not deferred:
                        if type(field) is models.ForeignKey:
                            params[field.name] = related_instance
                        else:
                            params[field.name] = [related_instance]
                else:
                    params[field.name] = \
                        DEFAULT_TEST_ATTRIBUTE_VALUES[type(field)]

        if not deferred:
            model(**params).save(**using_args)

    # Create all deferred models.
    if deferred_models:
        create_test_data(deferred_models, database)

    # All models should be created (Not all deferred fields have been populated
    # yet) Populate deferred fields that we know about.  Here lies untested
    # code!
    if deferred_fields:
        for model, field_list in deferred_fields.items():
            for field in field_list:
                related_model = field.rel.to
                related_instance = related_model.objects.using(database)[0]

                if type(field) is models.ForeignKey:
                    setattr(model, field.name, related_instance)
                else:
                    getattr(model, field.name).add(related_instance,
                                                   **using_args)

            model.save(**using_args)


def test_sql_mapping(test_field_name, db_name='default'):
    engine = settings.DATABASES[db_name]['ENGINE'].split('.')[-1]

    sql_for_engine = __import__('django_evolution.tests.db.%s' % (engine),
                                {}, {}, [''])

    return getattr(sql_for_engine, test_field_name)


def deregister_models(app_label='tests'):
    "Clear the test section of the app cache"
    unregister_app(app_label)


def set_app_test_models(models, app_label):
    """Sets the list of models in the Django test models registry."""
    register_app_models(app_label, models.items(), reset=True)


def add_app_test_model(model, app_label):
    """Adds a model to the Django test models registry."""
    register_app_models(app_label,
                        [(model._meta.object_name.lower(), model)])


def generate_index_name(db_type, table, col_names, field_names=None,
                        index_together=False):
    """Generate a suitable index name to test against.

    The returned index name is meant for use in the test data modules, and
    is used to compare our own expectations of how an index should be named
    with the naming Django provides in its own functions.

    Args:
        db_type (str):
            The database type for the index. Currently, only "postgres"
            does anything special.

        table (str):
            The name of the table the index refers to.

        col_names (str or list of str):
            The column name, or list of column names, for the index.

            This is used for Postgres (when not using ``index_together``),
            or for Django < 1.5. Otherwise, it's interchangeable with
            ``field_names``.

        field_names (str or list of str, optional):
            The field name, or list of field names, for the index.

            This is interchangeable with ``column_names`` on Django >= 1.5
            (unless using Postgres without ``index_together``), or when
            passing ``default=True``.

        index_together (bool, optional):
            Whether this index covers multiple fields indexed together
            through Django's ``Model._meta.index_together``.

            Defaults to ``False``.

    Returns:
        str:
        The resulting index name for the given criteria.
    """
    if not isinstance(col_names, list):
        col_names = [col_names]

    if field_names and not isinstance(field_names, list):
        field_names = [field_names]

    if not field_names:
        field_names = col_names

    assert len(field_names) == len(col_names)

    django_version = django.VERSION[:2]

    # Note that we're checking Django versions/engines specifically, since
    # we want to test that we're getting the right index names for the
    # right versions of Django, rather than asking Django for them.
    #
    # The order here matters.
    if django_version >= (1, 7):
        if len(col_names) == 1:
            assert not index_together

            # Django 1.7 went back to passing a single column name (and
            # not a list as a single variable argument) when there's only
            # one column.
            name = digest(connection, col_names[0])
        else:
            assert index_together

            index_unique_name = _generate_index_unique_name_hash(
                connection, table, col_names)
            name = '%s%s_idx' % (col_names[0], index_unique_name)
    elif db_type == 'postgres' and not index_together:
        # Postgres computes the index names separately from the rest of
        # the engines. It just uses '<tablename>_<colname>", same as
        # Django < 1.2. We only do this for normal indexes, though, not
        # index_together.
        name = col_names[0]
    elif django_version >= (1, 5):
        # Django >= 1.5 computed the digest of the representation of a
        # list of either field names or column names. Note that digest()
        # takes variable positional arguments, which this is not passing.
        # This is due to a design bug in these versions.
        name = digest(connection, field_names or col_names)
    elif django_version >= (1, 2):
        # Django >= 1.2, < 1.7 used the digest of the name of the first
        # column. There was no index_together in these releases.
        name = digest(connection, col_names[0])
    else:
        # Django < 1.2 used just the name of the first column, no digest.
        name = col_names[0]

    return truncate_name('%s_%s' % (table, name),
                         connection.ops.max_name_length())


def make_generate_index_name(db_type):
    """Return an index generation function for the given database type.

    This is used by the test data modules as a convenience to allow
    for a local version of :py:func:`generate_index_name` that doesn't need
    to be passed a database type on every call.

    Args:
        db_type (str):
            The database type to use. Currently, only "postgres" does anything
            special.

    Returns:
        callable:
        A version of :py:func:`generate_index_name` that doesn't need the
        ``db_type`` parameter.
    """
    return partial(generate_index_name, db_type)


def has_index_with_columns(database_sig, table_name, columns, unique=False):
    """Returns whether there's an index with the given criteria.

    This looks in the database signature for an index for the given table,
    column names, and with the given uniqueness flag. It will return a boolean
    indicating if one was found.
    """
    assert table_name in database_sig

    for index_info in database_sig[table_name]['indexes'].itervalues():
        if index_info['columns'] == columns and index_info['unique'] == unique:
            return True

    return False


def generate_constraint_name(db_type, r_col, col, r_table, table):
    """Return the expected name for a constraint.

    This will generate a constraint name for the current version of Django,
    for comparison purposes.

    Args:
        db_type (str):
            The type of database.

        r_col (str):
            The column name for the source of the relation.

        col (str):
            The column name for the "to" end of the relation.

        r_table (str):
            The table name for the source of the relation.

        table (str):
            The table name for the "to" end of the relation.

    Returns:
        str:
        The expected name for a constraint.
    """
    if django.VERSION[:2] >= (1, 7):
        # This is an approximation of what Django 1.7+ uses for constraint
        # naming. It's actually the same as index naming, but for test
        # purposes, we want to keep this distinct from the index naming above.
        # It also doesn't cover all the cases that
        # BaseDatabaseSchemaEditor._create_index_name covers, but they're not
        # necessary for our tests (and we'll know if it all blows up somehow).
        max_length = connection.ops.max_name_length() or 200
        index_unique_name = _generate_index_unique_name_hash(
            connection, r_table, [r_col])

        name = '_%s%s_fk_%s_%s' % (r_col, index_unique_name, table, col)
        full_name = '%s%s' % (r_table, name)

        if len(full_name) > max_length:
            full_name = '%s%s' % (r_table[:(max_length - len(name))], name)

        return full_name
    else:
        return '%s_refs_%s_%s' % (r_col, col,
                                  digest(connection, r_table, table))


def make_generate_constraint_name(db_type):
    """Return a constraint generation function for the given database type.

    This is used by the test data modules as a convenience to allow
    for a local version of :py:func:`generate_constraint_name` that doesn't
    need to be passed a database type on every call.

    Args:
        db_type (str):
            The database type to use. Currently, only "postgres" does anything
            special.

    Returns:
        callable:
        A version of :py:func:`generate_constraint_name` that doesn't need the
        ``db_type`` parameter.
    """
    return partial(generate_constraint_name, db_type)


def generate_unique_constraint_name(table, col_names):
    """Return the expected name for a unique constraint.

    This will generate a constraint name for the current version of Django,
    for comparison purposes.

    Args:
        table (str):
            The table name.

        col_names (list of str):
            The list of column names for the constraint.

    Returns:
        The expected constraint name for this version of Django.
    """
    if django.VERSION[:2] >= (1, 7):
        max_length = connection.ops.max_name_length() or 200
        index_unique_name = _generate_index_unique_name_hash(
            connection, table, col_names)
        name = '_%s%s_uniq' % (col_names[0], index_unique_name)
        full_name = '%s%s' % (table, name)

        if len(full_name) > max_length:
            full_name = '%s%s' % (table[:(max_length - len(name))], name)

        return full_name
    else:
        name = digest(connection, col_names)

        return truncate_name('%s_%s' % (table, name),
                             connection.ops.max_name_length())


def _generate_index_unique_name_hash(connection, table, col_names):
    """Return the hash for the unique part of an index name.

    This is used on Django 1.7+ to generate a unique hash as part of an
    index name.

    Args:
        connection (object):
            The database connection.

        table (str):
            The name of the table.

        col_names (list of str):
            The list of column names for the index.

    Returns:
        str:
        A hash for the unique part of an index.
    """
    assert isinstance(col_names, list)

    if django.VERSION[:2] >= (1, 9):
        # Django >= 1.9
        #
        # Django 1.9 introduced a new format for the unique index hashes,
        # switching back to using digest() instead of hash().
        return '_%s' % digest(connection, table, *col_names)
    else:
        # Django >= 1.7, < 1.9
        return '_%x' % abs(hash((table, ','.join(col_names))))

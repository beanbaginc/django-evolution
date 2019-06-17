"""Utility functions for working with Django Migrations."""

from __future__ import unicode_literals

from importlib import import_module

try:
    # Django >= 1.7
    from django.core.management.sql import (emit_post_migrate_signal,
                                            emit_pre_migrate_signal)
    from django.db.migrations.executor import MigrationExecutor
    from django.db.migrations.exceptions import InconsistentMigrationHistory
    from django.db.migrations.recorder import MigrationRecorder
    from django.db.migrations.state import ModelState
except ImportError:
    # Django < 1.7
    InconsistentMigrationHistory = None
    MigrationExecutor = None
    MigrationRecorder = None
    ModelState = None
    emit_post_migrate_signal = None
    emit_pre_migrate_signal = None

from django_evolution.compat.models import get_model
from django_evolution.support import supports_migrations
from django_evolution.utils.apps import get_app_name


def has_migrations_module(app):
    """Return whether an app has a migrations module.

    Args:
        app (module):
            The app module.

    Returns:
        bool:
        ``True`` if the app has a ``migrations`` module. ``False`` if it
        does not.
    """
    app_name = get_app_name(app)

    try:
        import_module('%s.migrations' % app_name)
        return True
    except ImportError:
        return False


def get_applied_migrations_by_app(connection):
    """Return all applied migration names organized by app label.

    This can only be called when on Django 1.7 or higher.

    Args:
        connection (django.db.backends.base.BaseDatabaseWrapper):
            The connection used to look up recorded migrations.

    Returns:
        dict:
        A dictionary mapping app labels to sets of applied migration names.
    """
    assert supports_migrations, \
        'This cannot be called on Django 1.6 or earlier.'

    recorder = MigrationRecorder(connection)
    applied_migrations = recorder.applied_migrations()
    by_app = {}

    for app_label, migration_name in applied_migrations:
        by_app.setdefault(app_label, set()).add(migration_name)

    return by_app


def record_applied_migrations(connection, app_label, migration_names):
    """Record a list of applied migrations to the database.

    Note that, due to the underlying mechanisms in Django, this will record
    each migration one-by-one, using multiple SQL queries.

    This can only be called when on Django 1.7 or higher.

    Args:
        connection (django.db.backends.base.BaseDatabaseWrapper):
            The connection used to record applied migrations.

        app_label (unicode):
            The app label that the migrations pertain to.

        migration_names (list of unicode):
            The list of migration names to record as applied.
    """
    assert supports_migrations, \
        'This cannot be called on Django 1.6 or earlier.'

    recorder = MigrationRecorder(connection)

    for migration_name in migration_names:
        recorder.record_applied(app_label, migration_name)


def filter_migration_targets(targets, app_labels):
    """Filter migration execution targets to those in the specified app labels.

    Args:
        targets (list of tuple):
            The migration targets to be executed.

        app_labels (set of unicode):
            The app labels to limit the targets to.

    Returns:
        list of tuple:
        The resulting list of migration targets.
    """
    if not isinstance(app_labels, set):
        app_labels = set(app_labels)

    return [
        key
        for key in targets
        if key[0] in app_labels
    ]


def apply_migrations(executor, targets, plan):
    """Apply migrations to the database.

    Migrations will be applied using the ``fake_initial`` mode, which means
    that any initial migrations (those constructing the models for an app)
    will be skipped if the models already appear in the database. This is to
    avoid issues with applying those migrations when the models have already
    been created in the past outside of Django's Migrations framework. In
    theory, this could cause some issues if those migrations also perform
    other important operations around data population, but this is really up
    to Django to handle, as this is part of the upgrade method when going
    from pre-1.7 to 1.7+ anyway.

    This can only be called when on Django 1.7 or higher.

    Args:
        executor (django.db.migrations.executor.MigrationExecutor):
            The migration executor that will handle applying the migrations.

        targets (list of tuple):
            The list of migration targets to apply.

        plan (list of tuple):
            The order in which migrations will be applied.
    """
    assert supports_migrations, \
        'This cannot be called on Django 1.6 or earlier.'

    db_name = executor.connection.alias

    # Unfortunately, we have to call into a private method here, just as the
    # migrate command does. Ideally, this would be official API.
    pre_migrate_state = executor._create_project_state(
        with_applied_migrations=True)

    # TODO: Replace with our own signal. Emit this in the management
    #       command, where verbosity/interactivity can be controlled.
    emit_pre_migrate_signal(
        verbosity=1,
        interactive=False,
        db=db_name,
        apps=pre_migrate_state.apps,
        plan=plan)

    post_migrate_state = executor.migrate(
        targets,
        plan=plan,
        state=pre_migrate_state.clone(),
        fake_initial=True)
    post_migrate_state.clear_delayed_apps_cache()

    post_migrate_apps = post_migrate_state.apps
    model_keys = []

    with post_migrate_apps.bulk_update():
        for model_state in post_migrate_apps.real_models:
            model_key = (model_state.app_label, model_state.name_lower)
            model_keys.append(model_key)
            post_migrate_apps.unregister_model(*model_key)

    post_migrate_apps.render_multiple([
        ModelState.from_model(get_model(*model))
        for model in model_keys
    ])

    # TODO: Replace with our own signal. Emit this in the management
    #       command, where verbosity/interactivity can be controlled.
    emit_post_migrate_signal(
        verbosity=1,
        interactive=False,
        db=db_name,
        apps=post_migrate_apps,
        plan=plan)

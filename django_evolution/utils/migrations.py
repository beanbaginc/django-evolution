"""Utility functions for working with Django Migrations."""

from __future__ import unicode_literals

from importlib import import_module

import django
from django.utils import six

try:
    # Django >= 1.7
    from django.core.management.sql import (emit_post_migrate_signal,
                                            emit_pre_migrate_signal)
    from django.db.migrations.executor import (MigrationExecutor as
                                               DjangoMigrationExecutor)
    from django.db.migrations.loader import (MigrationLoader as
                                             DjangoMigrationLoader)
    from django.db.migrations.recorder import MigrationRecorder
    from django.db.migrations.state import ModelState
except ImportError:
    # Django < 1.7
    DjangoMigrationExecutor = object
    DjangoMigrationLoader = object
    MigrationRecorder = None
    ModelState = None
    emit_post_migrate_signal = None
    emit_pre_migrate_signal = None

from django_evolution.compat.models import get_model
from django_evolution.errors import (MigrationConflictsError,
                                     MigrationHistoryError)
from django_evolution.signals import applied_migration, applying_migration
from django_evolution.support import supports_migrations
from django_evolution.utils.apps import get_app_name


class MigrationLoader(DjangoMigrationLoader):
    """Loads migration files from disk.

    This is a specialization of Django's own
    :py:class:`~django.db.migrations.loader.MigrationLoader` that allows for
    providing additional migrations not available on disk.

    Attributes:
        extra_applied_migrations (set of tuple):
            Migrations to mark as already applied. This can be used to
            augment the results calculated from the database.

            Each tuple is in the form of ``(app_label, migration_name)``.
    """

    def __init__(self, connection, custom_migrations=None, *args, **kwargs):
        """Initialize the loader.

        Args:
            connection (django.db.backends.base.BaseDatabaseWrapper):
                The connection to load applied migrations from.

            custom_migrations (dict, optional):
                Custom migrations not available on disk. Each key is a tuple
                of ``(app_label, migration_name)``, and each value is a
                migration.

            *args (tuple):
                Additional positional arguments for the parent class.

            **kwargs (dict):
                Additional keyword arguments for the parent class.
        """
        self._custom_migrations = custom_migrations or {}
        self._applied_migrations = set()

        self.extra_applied_migrations = set()

        super(MigrationLoader, self).__init__(connection, *args, **kwargs)

    @property
    def applied_migrations(self):
        """The migrations already applied.

        This will contain both the migrations applied from the database
        and any set in :py:attr:`extra_applied_migrations`.
        """
        return self._applied_migrations | self.extra_applied_migrations

    @applied_migrations.setter
    def applied_migrations(self, value):
        """Set the migrations already applied.

        Args:
            value (set of tuple):
                The migrations already applied to the database.
        """
        self._applied_migrations = value

    def load_disk(self):
        """Load migrations from disk.

        This will also load any custom migrations.
        """
        super(MigrationLoader, self).load_disk()

        for key, migration in six.iteritems(self._custom_migrations):
            app_label = key[0]

            self.migrated_apps.add(app_label)
            self.unmigrated_apps.discard(app_label)
            self.disk_migrations[key] = migration


class MigrationExecutor(DjangoMigrationExecutor):
    """Load and execute migrations.

    This is a specialization of Django's own
    :py:class:`~django.db.migrations.executor.MigrationExecutor` that allows
    for providing additional migrations not available on disk, and for
    emitting our own signals when processing migrations.
    """

    def __init__(self, connection, custom_migrations=None, signal_sender=None):
        """Initialize the executor.

        Args:
            connection (django.db.backends.base.BaseDatabaseWrapper):
                The connection to load applied migrations from.

            custom_migrations (dict, optional):
                Custom migrations not available on disk. Each key is a tuple
                of ``(app_label, migration_name)``, and each value is a
                migration.

            signal_sender (object, optional):
                A custom sender to pass when sending signals. This defaults
                to this instance.
        """
        self._signal_sender = signal_sender or self

        super(MigrationExecutor, self).__init__(
            connection=connection,
            progress_callback=self._on_progress)

        # Ideally we would be able to replace this during initialization,
        # or at the very least prevent the default one from loading from
        # disk, but it's not often that these will be constructed, so it's
        # probably fine.
        self.loader = MigrationLoader(connection=connection,
                                      custom_migrations=custom_migrations)

    def run_checks(self):
        """Perform checks on the migrations and any history.

        Raises:
            django_evolution.errors.MigrationConflictsError:
                There are conflicts between migrations loaded from disk.

            django_evolution.errors.MigrationHistoryError:
                There are unapplied dependencies to applied migrations.
        """
        # Make sure that the migration files in the tree form a proper history.
        if hasattr(self.loader, 'check_consistent_history'):
            # Django >= 1.10
            from django.db.migrations.exceptions import \
                InconsistentMigrationHistory

            try:
                self.loader.check_consistent_history(self.connection)
            except InconsistentMigrationHistory as e:
                raise MigrationHistoryError(six.text_type(e))

        # Now check that there aren't any conflicts between any migrations that
        # we may end up working with.
        conflicts = self.loader.detect_conflicts()

        if conflicts:
            raise MigrationConflictsError(conflicts)

    def _on_progress(self, action, migration=None, *args, **kwargs):
        """Handler for progress notifications.

        This will convert certain progress notifications to Django Evolution
        signals.

        Args:
            action (unicode):
                The action reflecting the progress update.

            migration (django.db.migrations.Migration, optional):
                The migration that the progress update applies to. This is
                not provided for all progress updates.

            *args (tuple, unused):
                Additional positional arguments passed for the update.

            **kwargs (dict, unused):
                Additional keyword arguments passed for the update.
        """
        if action == 'apply_start':
            applying_migration.send(sender=self._signal_sender,
                                    migration=migration)
        elif action == 'apply_success':
            applied_migration.send(sender=self._signal_sender,
                                   migration=migration)


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


def record_applied_migrations(connection, migration_targets):
    """Record a list of applied migrations to the database.

    This can only be called when on Django 1.7 or higher.

    Args:
        connection (django.db.backends.base.BaseDatabaseWrapper):
            The connection used to record applied migrations.

        migration_targets (list of tuple):
            The list of migration targets to record as applied. Each tuple
            is in the form of ``(app_label, migration_name)``.
    """
    assert supports_migrations, \
        'This cannot be called on Django 1.6 or earlier.'

    recorder = MigrationRecorder(connection)
    recorder.ensure_schema()

    recorder.migration_qs.bulk_create(
        recorder.Migration(app=app_label,
                           name=migration_name)
        for app_label, migration_name in migration_targets
    )


def unrecord_applied_migrations(connection, app_label, migration_names=None):
    """Remove the recordings of applied migrations from the database.

    This can only be called when on Django 1.7 or higher.

    Args:
        connection (django.db.backends.base.BaseDatabaseWrapper):
            The connection used to unrecord applied migrations.

        app_label (unicode):
            The app label that the migrations pertain to.

        migration_names (list of unicode, optional):
            The list of migration names to unrecord. If not provided, all
            migrations for the app will be unrecorded.
    """
    assert supports_migrations, \
        'This cannot be called on Django 1.6 or earlier.'

    recorder = MigrationRecorder(connection)
    recorder.ensure_schema()

    queryset = recorder.migration_qs.filter(app=app_label)

    if migration_names:
        queryset = queryset.filter(name__in=migration_names)

    queryset.delete()


def filter_migration_targets(targets, app_labels=None, exclude=None):
    """Filter migration execution targets based on the given criteria.

    Args:
        targets (list of tuple):
            The migration targets to be executed.

        app_labels (set of unicode, optional):
            The app labels to limit the targets to.

        exclude (set, optional):
            Explicit targets to exclude.

    Returns:
        list of tuple:
        The resulting list of migration targets.
    """
    if app_labels is not None:
        if not isinstance(app_labels, set):
            app_labels = set(app_labels)

        targets = (
            target
            for target in targets
            if target[0] in app_labels
        )

    if exclude:
        if not isinstance(exclude, set):
            exclude = set(exclude)

        targets = (
            target
            for target in targets
            if target not in exclude
        )

    return list(targets)


def is_migration_initial(migration):
    """Return whether a migration is an initial migration.

    Initial migrations are those that set up an app or models for the first
    time. Generally, they should be limited to model creations, or to those
    adding fields to a (non-migration-aware) model for the first time. They
    also should not have any dependencies on other migrations within the same
    app.

    An initial migration should be able to be safely soft-applied (in other
    words, ignored if the model already appears to exist in the database).

    Migrations on Django 1.9+ may declare themselves as explicitly initial
    or explicitly not initial.

    Args:
        migration (django.db.migrations.Migration):
            The migration to check.

    Returns:
        bool:
        ``True`` if the migration appears to be an initial migration.
        ``False`` if it does not.
    """
    # NOTE: The general logic here is based on the checks done in
    #       MigrationExecutor.detect_soft_applied.

    # Migration.initial was introduced in Django 1.9.
    initial = getattr(migration, 'initial', None)

    if initial is False:
        return False
    elif initial is None:
        # If the migration has any dependencies within the same app, it can't
        # be initial.
        for dep_app_label, dep_app_name in migration.dependencies:
            if dep_app_label == migration.app_label:
                return False

    return True


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

    pre_signal_kwargs = {
        'db': db_name,
        'interactive': False,
        'verbosity': 1,
    }
    post_signal_kwargs = pre_signal_kwargs.copy()

    migrate_kwargs = {
        'fake': False,
        'plan': plan,
        'targets': targets,
    }

    django_version = django.VERSION[:2]

    # Build version-dependent state needed for the signals and migrate
    # operation.
    if (1, 7) <= django_version <= (1, 8):
        pre_signal_kwargs['create_models'] = []
        post_signal_kwargs['created_models'] = []

    if django_version >= (1, 8):
        # Mark any migrations that introduce new models that are already in
        # the database as applied.
        migrate_kwargs['fake_initial'] = True

    if django_version >= (1, 10):
        # Unfortunately, we have to call into a private method here, just as
        # the migrate command does. Ideally, this would be official API.
        pre_migrate_state = executor._create_project_state(
            with_applied_migrations=True)
        pre_signal_kwargs.update({
            'apps': pre_migrate_state.apps,
            'plan': plan,
        })
        migrate_kwargs['state'] = pre_migrate_state.clone()

    # TODO: Replace with our own signal. Emit this in the management
    #       command, where verbosity/interactivity can be controlled.
    emit_pre_migrate_signal(**pre_signal_kwargs)

    # Perform the migration and record the result. This only returns a value
    # on Django >= 1.10.
    post_migrate_state = executor.migrate(**migrate_kwargs)

    if django_version >= (1, 10):
        # On Django 1.10, we have a few more steps for generating the state
        # needed for the signal.
        if django_version >= (1, 11):
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

        post_signal_kwargs.update({
            'apps': post_migrate_apps,
            'plan': plan,
        })

    # TODO: Replace with our own signal. Emit this in the management
    #       command, where verbosity/interactivity can be controlled.
    emit_post_migrate_signal(**post_signal_kwargs)

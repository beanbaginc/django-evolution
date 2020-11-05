"""Utility functions for working with Django Migrations."""

from __future__ import unicode_literals

from importlib import import_module

import django

try:
    # Django >= 1.7
    from django.core.management.sql import (emit_post_migrate_signal,
                                            emit_pre_migrate_signal)
    from django.db.migrations import Migration
    from django.db.migrations.executor import (MigrationExecutor as
                                               DjangoMigrationExecutor)
    from django.db.migrations.loader import (MigrationLoader as
                                             DjangoMigrationLoader)
    from django.db.migrations.recorder import MigrationRecorder
    from django.db.migrations.state import ModelState

    emit_post_sync_signal = None
    emit_pre_sync_signal = None
except ImportError:
    # Django < 1.7
    from django.core.management.sql import (emit_post_sync_signal,
                                            emit_pre_sync_signal)

    DjangoMigrationExecutor = object
    DjangoMigrationLoader = object
    Migration = None
    MigrationRecorder = None
    ModelState = None
    emit_post_migrate_signal = None
    emit_pre_migrate_signal = None

from django_evolution.compat import six
from django_evolution.compat.models import get_model
from django_evolution.errors import (DjangoEvolutionSupportError,
                                     MigrationConflictsError,
                                     MigrationHistoryError)
from django_evolution.signals import applied_migration, applying_migration
from django_evolution.support import supports_migrations
from django_evolution.utils.apps import get_app_name


django_version = django.VERSION[:2]


class MigrationList(object):
    """A list of applied or pending migrations.

    This is used to manage a list of migrations in a way that's independent
    from the underlying representation used in Django. Migrations are tracked
    by app label and name, may be associated with a recorded migration
    database entry, and can be used to convert state to and from both
    signatures and Django migration state.
    """

    @classmethod
    def from_app_sig(cls, app_sig):
        """Create a MigrationList based on an app signature.

        Args:
            app_sig (django_evolution.signature.AppSignature):
                The app signature containing a list of applied migrations.

        Returns:
            MigrationList:
            The new migration list.
        """
        return cls.from_names(app_label=app_sig.app_id,
                              migration_names=app_sig.applied_migrations)

    @classmethod
    def from_names(cls, app_label, migration_names):
        """Create a MigrationList based on a list of migration names.

        Version Added:
            2.1

        Args:
            app_label (unicode):
                The app label common to each migration name.

            migration_names (list of unicode):
                The list of migration names.

        Returns:
            MigrationList:
            The new migration list.
        """
        migration_list = cls()

        if migration_names:
            for name in migration_names:
                migration_list.add_migration_info(app_label=app_label,
                                                  name=name)

        return migration_list

    @classmethod
    def from_database(cls, connection, app_label=None):
        """Create a MigrationList based on recorded migrations.

        Args:
            connection (django.db.backends.base.BaseDatabaseWrapper):
                The database connection used to query for migrations.

            app_label (unicode, optional):
                An app label to filter migrations by.

        Returns:
            MigrationList:
            The new migration list.
        """
        recorder = MigrationRecorder(connection)
        recorder.ensure_schema()

        migration_list = cls()
        queryset = recorder.migration_qs

        if app_label:
            queryset = queryset.filter(app=app_label)

        for recorded_migration in queryset.all():
            migration_list.add_recorded_migration(recorded_migration)

        return migration_list

    def __init__(self):
        """Initialize the list."""
        self._by_app_label = {}
        self._by_id = {}

    def has_migration_info(self, app_label, name):
        """Return whether the list contains an entry for a migration.

        Args:
            app_label (unicode):
                The label for the application that was migrated.

            name (unicode):
                The name of the migration.

        Returns:
            bool:
            ``True`` if the migration is in the list. ``False`` if it is not.
        """
        return (app_label, name) in self._by_id

    def add_migration_targets(self, targets):
        """Add a list of migration targets to the list.

        Args:
            targets (list of tuple):
                The migration targets to each. Each is a tuple containing
                an app label and a migration name.
        """
        for app_label, name in targets:
            self.add_migration_info(app_label=app_label,
                                    name=name)

    def add_migration(self, migration):
        """Add a migration to the list.

        This can only be called on Django 1.7 or higher.

        Args:
            migration (django.db.migrations.Migration):
                The migration instance to add.
        """
        assert Migration is not None
        assert isinstance(migration, Migration)

        self.add_migration_info(app_label=migration.app_label,
                                name=migration.name,
                                migration=migration)

    def add_recorded_migration(self, recorded_migration):
        """Add a recorded migration to the list.

        This can only be called on Django 1.7 or higher.

        Args:
            recorded_migration (django.db.migrations.recorder.
                                MigrationRecorder.Migration):
                The recorded migration model to add.
        """
        assert MigrationRecorder is not None
        assert isinstance(recorded_migration, MigrationRecorder.Migration)

        self.add_migration_info(app_label=recorded_migration.app,
                                name=recorded_migration.name,
                                recorded_migration=recorded_migration)

    def add_migration_info(self, app_label, name, migration=None,
                           recorded_migration=None):
        """Add information on a migration to the list.

        Args:
            app_label (unicode):
                The label for the application that was migrated.

            name (unicode):
                The name of the migration.

            migration (django.db.migrations.Migration, optional):
                An optional migration instance to associate with this entry.

            recorded_migration (django.db.migrations.recorder.
                                MigrationRecorder.Migration, optional):
                An optional recorded migration to associate with this entry.
        """
        info = {
            'app_label': app_label,
            'migration': migration,
            'name': name,
            'recorded_migration': recorded_migration,
        }

        self._by_app_label.setdefault(app_label, []).append(info)
        self._by_id[(app_label, name)] = info

    def update(self, other):
        """Update the list with the contents of another list.

        If there's an entry in another list matching this one, and contains
        information that the entry in this list does not have, this list's
        entry will be updated.

        Args:
            other (MigrationList):
                The list of migrations to put into this list.
        """
        for other_info in other:
            app_label = other_info['app_label']
            name = other_info['name']
            info = self._by_id.get((app_label, name))

            if info is None:
                self.add_migration_info(app_label=app_label,
                                        name=name)
            else:
                for key in ('migration', 'recorded_migration'):
                    if info[key] is None:
                        info[key] = other_info[key]

    def to_targets(self):
        """Return a set of migration targets based on this list.

        Returns:
            set:
            A set of migration targets. Each entry is a tuple containing
            the app label and name.
        """
        return set(
            (info['app_label'], info['name'])
            for info in self
        )

    def get_app_labels(self):
        """Iterate through the app labels.

        Results are sorted alphabetically.

        Returns:
            list of unicode:
            The sorted list of app labels with associated migrations.
        """
        return list(sorted(six.iterkeys(self._by_app_label)))

    def clone(self):
        """Clone the list.

        Returns:
            MigrationList:
            The cloned migration list.
        """
        new_migration_list = MigrationList()

        for info in self:
            new_migration_list.add_migration_info(**info)

        return new_migration_list

    def __bool__(self):
        """Return whether this list is truthy or falsy.

        The list is truthy only if it has items.

        Returns:
            bool:
            ``True`` if the list has items. ``False`` if it's empty.
        """
        return bool(self._by_id)

    def __len__(self):
        """Return the number of items in the list.

        Returns:
            int:
            The number of items in the list.
        """
        return len(self._by_id)

    def __eq__(self, other):
        """Return whether this list is equal to another list.

        The order of migrations is ignored when comparing lists.

        Args:
            other (MigrationList):
                A list of migrations to compare to.

        Returns:
            bool:
            ``True`` if the two lists have the same contents. ``False`` if
            there are differences in contents, or ``other`` is not a
            :py:class:`MigrationList`.
        """
        if other is None or not isinstance(other, MigrationList):
            return False

        return self._by_id == other._by_id

    def __iter__(self):
        """Iterate through the list.

        Entries are sorted first by app label, alphabetically, and then
        the order in which migrations were added for that app label.

        Yields:
            info:
            A dictionary containing the following keys:

            ``app_label`` (:py:class:`unicode`):
                The app label for the migration.

            ``name`` (:py:class:`unicode`):
                The name of the migration.

            ``migration`` (:py:class:`django.db.migrations.Migration`):
                The optional migration instance.

            ``recorded_migration`` (:py:class:`django.db.migrations.recorder.MigrationRecorder.Migration`):
                The optional recorded migration.
        """
        for app_label, info_list in sorted(six.iteritems(self._by_app_label),
                                           key=lambda pair: pair[0]):
            for info in info_list:
                yield info

    def __add__(self, other):
        """Return a combined copy of this list and another list.

        Args:
            other (MigrationList):
                The other list to add to this list.

        Returns:
            MigrationList:
            The new migration list containing contents of both lists.
        """
        new_migration_list = self.clone()
        new_migration_list.update(other)

        return new_migration_list

    def __sub__(self, other):
        """Return a copy of this list with another list's contents excluded.

        Args:
            other (MigrationList):
                The other list containing contents to exclude.

        Returns:
            MigrationList:
            The new migration list containing the contents of this list that
            don't exist in the other list.
        """
        new_migration_list = MigrationList()

        for info in self:
            if not other.has_migration_info(app_label=info['app_label'],
                                            name=info['name']):
                new_migration_list.add_migration_info(**info)

        return new_migration_list

    def __repr__(self):
        """Return a string representation of this list.

        Returns:
            unicode:
            The string representation.
        """
        return '<MigrationList%s>' % list(self)


class MigrationLoader(DjangoMigrationLoader):
    """Loads migration files from disk.

    This is a specialization of Django's own
    :py:class:`~django.db.migrations.loader.MigrationLoader` that allows for
    providing additional migrations not available on disk.

    Attributes:
        extra_applied_migrations (MigrationList):
            Migrations to mark as already applied. This can be used to
            augment the results calculated from the database.
    """

    def __init__(self, connection, custom_migrations=None, *args, **kwargs):
        """Initialize the loader.

        Args:
            connection (django.db.backends.base.BaseDatabaseWrapper):
                The connection to load applied migrations from.

            custom_migrations (MigrationList, optional):
                Custom migrations not available on disk.

            *args (tuple):
                Additional positional arguments for the parent class.

            **kwargs (dict):
                Additional keyword arguments for the parent class.
        """
        self._custom_migrations = custom_migrations or MigrationList()
        self._applied_migrations = None
        self._lock_migrations = False

        self.extra_applied_migrations = MigrationList()

        super(MigrationLoader, self).__init__(connection, *args, **kwargs)

    @property
    def applied_migrations(self):
        """The migrations already applied.

        This will contain both the migrations applied from the database
        and any set in :py:attr:`extra_applied_migrations`.
        """
        extra_migrations = self.extra_applied_migrations

        if isinstance(self._applied_migrations, dict):
            # Django >= 3.0
            applied_migrations = self._applied_migrations.copy()

            for info in extra_migrations:
                app_label = info['app_label']
                name = info['name']
                recorded_migration = info['recorded_migration']

                if recorded_migration is None:
                    recorded_migration = MigrationRecorder.Migration(
                        app=app_label,
                        name=name,
                        applied=True)

                applied_migrations[(app_label, name)] = recorded_migration

        elif isinstance(self._applied_migrations, set):
            # Django < 3.0
            applied_migrations = self._applied_migrations | set(
                (info['app_label'], info['name'])
                for info in extra_migrations
            )
        else:
            raise DjangoEvolutionSupportError(
                'Migration.applied_migrations is an unexpected type (%s)'
                % type(self._applied_migrations))

        return applied_migrations

    @applied_migrations.setter
    def applied_migrations(self, value):
        """Set the migrations already applied.

        Args:
            value (set of tuple):
                The migrations already applied to the database.
        """
        if value is not None and not isinstance(value, (dict, set)):
            raise DjangoEvolutionSupportError(
                'Migration.applied_migrations was set to an unexpected type '
                '(%s)'
                % type(value))

        if value is None:
            self._applied_migrations = None
        else:
            if django_version >= (3, 0):
                self._applied_migrations = dict(value)
            else:
                self._applied_migrations = value

    def build_graph(self, reload_migrations=True):
        """Rebuild the migrations graph.

        Args:
            reload_migrations (bool, optional):
                Whether to reload migration instances from disk. If ``False``,
                the ones loaded before will be used.
        """
        if not reload_migrations:
            self._lock_migrations = True

        try:
            super(MigrationLoader, self).build_graph()
        finally:
            self._lock_migrations = False

    def load_disk(self):
        """Load migrations from disk.

        This will also load any custom migrations.
        """
        if self._lock_migrations:
            return

        super(MigrationLoader, self).load_disk()

        for info in self._custom_migrations:
            migration = info['migration']
            assert migration is not None

            app_label = info['app_label']
            name = info['name']

            self.migrated_apps.add(app_label)
            self.unmigrated_apps.discard(app_label)
            self.disk_migrations[(app_label, name)] = migration


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


def record_applied_migrations(connection, migrations):
    """Record a list of applied migrations to the database.

    This can only be called when on Django 1.7 or higher.

    Args:
        connection (django.db.backends.base.BaseDatabaseWrapper):
            The connection used to record applied migrations.

        migrations (MigrationList):
            The list of migration targets to record as applied.
    """
    assert supports_migrations, \
        'This cannot be called on Django 1.6 or earlier.'

    recorder = MigrationRecorder(connection)
    recorder.ensure_schema()

    recorder.migration_qs.bulk_create(
        recorder.Migration(app=info['app_label'],
                           name=info['name'])
        for info in migrations
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


def create_pre_migrate_state(executor):
    """Create state needed before migrations are applied.

    The return value is dependent on the version of Django.

    Args:
        executor (django.db.migrations.executor.MigrationExecutor):
            The migration executor that will handle the migrations.

    Returns:
        django.db.migrations.state.ProjectState:
        The state needed for applying migrations.
    """
    assert supports_migrations, \
        'This cannot be called on Django 1.6 or earlier.'

    if django_version >= (1, 10):
        # Unfortunately, we have to call into a private method here, just as
        # the migrate command does. Ideally, this would be official API.
        return executor._create_project_state(with_applied_migrations=True)

    return None


def apply_migrations(executor, targets, plan, pre_migrate_state):
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

        pre_migrate_state (object):
            The pre-migration state needed to apply these migrations.
            This must be generated with :py:func:`create_pre_migrate_state`
            or a previous call to :py:func:`apply_migrations`.

    Returns:
        object:
        The state generated from applying migrations. Any final state must
        be passed to :py:func:`finalize_migrations`.
    """
    assert supports_migrations, \
        'This cannot be called on Django 1.6 or earlier.'

    migrate_kwargs = {
        'fake': False,
        'plan': plan,
        'targets': targets,
    }

    # Build version-dependent state needed for the signals and migrate
    # operation.
    if django_version >= (1, 8):
        # Mark any migrations that introduce new models that are already in
        # the database as applied.
        migrate_kwargs['fake_initial'] = True

    if django_version >= (1, 10):
        migrate_kwargs['state'] = pre_migrate_state.clone()

    # Perform the migration and record the result. This only returns a value
    # on Django >= 1.10.
    return executor.migrate(**migrate_kwargs)


def finalize_migrations(post_migrate_state):
    """Finalize any migrations operations.

    This will update any internal state in Django for any migrations that
    were applied and represented by the provided post-migrate state.

    Args:
        post_migrate_state (object):
            The state generated from applying migrations. This must be the
            result of :py:meth:`apply_migrations`.
    """
    assert supports_migrations, \
        'This cannot be called on Django 1.6 or earlier.'

    if django_version >= (1, 10):
        # On Django 1.10, we have a few more steps for generating the state
        # needed for the signal.
        if django_version >= (1, 11):
            post_migrate_state.clear_delayed_apps_cache()

        post_migrate_apps = post_migrate_state.apps
        assert post_migrate_apps is not None

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


def emit_pre_migrate_or_sync(verbosity, interactive, database_name,
                             create_models, pre_migrate_state, plan):
    """Emit the pre_migrate and/or pre_sync signals.

    This will emit the :py:data:`~django.db.models.signals.pre_migrate`
    and/or :py:data:`~django.db.models.signals.pre_sync` signals, providing
    the appropriate arguments for the current version of Django.

    Args:
        verbosity (int):
            The verbosity level for output.

        interactive (bool):
            Whether handlers of the signal can prompt on the terminal for
            input.

        database_name (unicode):
            The name of the database being migrated.

        create_models (list of django.db.models.Model):
            The list of models being created outside of any migrations.

        pre_migrate_state (django.db.migrations.state.ProjectState):
            The project state prior to any migrations.

        plan (list):
            The full migration plan being applied.
    """
    emit_kwargs = {
        'db': database_name,
        'interactive': interactive,
        'verbosity': verbosity,
    }

    if django_version <= (1, 8):
        emit_kwargs['create_models'] = create_models
    elif django_version >= (1, 10):
        if pre_migrate_state:
            apps = pre_migrate_state.apps
        else:
            apps = None

        emit_kwargs.update({
            'apps': apps,
            'plan': plan,
        })

    if emit_pre_sync_signal:
        emit_pre_sync_signal(**emit_kwargs)
    else:
        emit_pre_migrate_signal(**emit_kwargs)


def emit_post_migrate_or_sync(verbosity, interactive, database_name,
                              created_models, post_migrate_state, plan):
    """Emit the post_migrate and/or post_sync signals.

    This will emit the :py:data:`~django.db.models.signals.post_migrate`
    and/or :py:data:`~django.db.models.signals.post_sync` signals, providing
    the appropriate arguments for the current version of Django.

    Args:
        verbosity (int):
            The verbosity level for output.

        interactive (bool):
            Whether handlers of the signal can prompt on the terminal for
            input.

        database_name (unicode):
            The name of the database that was migrated.

        created_models (list of django.db.models.Model):
            The list of models created outside of any migrations.

        post_migrate_state (django.db.migrations.state.ProjectState):
            The project state after applying migrations.

        plan (list):
            The full migration plan that was applied.
    """
    emit_kwargs = {
        'db': database_name,
        'interactive': interactive,
        'verbosity': verbosity,
    }

    if django_version <= (1, 8):
        emit_kwargs['created_models'] = created_models
    elif django_version >= (1, 10):
        if post_migrate_state:
            apps = post_migrate_state.apps
        else:
            apps = None

        emit_kwargs.update({
            'apps': apps,
            'plan': plan,
        })

    if emit_post_sync_signal:
        emit_post_sync_signal(**emit_kwargs)
    else:
        emit_post_migrate_signal(**emit_kwargs)

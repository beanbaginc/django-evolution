"""Classes for working with stored evolution state signatures.

These provide a way to work with the state of Django apps and their models in
an abstract way, and to deserialize from or serialize to a string. Signatures
can also be diffed, showing the changes between an older and a newer version
in order to help see how the current database's signature differs from an older
stored version.

Serialized versions of signatures are versioned, and the signature classes
handle loading and saving as any version. However, state may be lost when
downgrading a signature.

The following versions are currently supported:

Version 1:
    The original version of the signature, used up until Django Evolution
    1.0. This is in the form of::

        {
            '__version__': 1,
            '<legacy_app_label>': {
                '<model_name>': {
                    'meta': {
                        'db_table': '<table name>',
                        'db_tablespace': '<tablespace>',
                        'index_together': [
                            ('<colname>', ...),
                            ...
                        ],
                        'indexes': [
                            {
                                'name': '<name>',
                                'fields': ['<colname>', ...],
                            },
                            ...
                        ],
                        'pk_column': '<colname>',
                        'unique_together': [
                            ('<colname>', ...),
                            ...
                        ],
                        '__unique_together_applied': True|False,
                    },
                    'fields': {
                        'field_type': <class>,
                        'related_model': '<app_label>.<class_name>',
                        '<field_attr>': <value>,
                        ...
                    },
                },
                ...
            },
            ...
        }


Version 2:
    Introduced in Django Evolution 2.0. This differs from version 1 in
    that it's deeper, with explicit namespaces for apps, models, and
    field attributes that can exist alongside metadata keys. This is
    in the form of::

        {
            '__version__': 2,
            'apps': {
                '<app_label>': {
                    'legacy_app_label': '<legacy app_label>',
                    'upgrade_method': 'migrations'|'evolutions'|None,
                    'applied_migrations' ['<migration name>', ...],
                    'models': {
                        '<model_name>': {
                            'meta': {
                                'constraints': [
                                    {
                                        'name': '<name>',
                                        'type': '<class_path>',
                                        'attrs': {
                                            '<attr_name>': <value>,
                                        },
                                    },
                                    ...
                                ],
                                'db_table': '<table name>',
                                'db_tablespace': '<tablespace>',
                                'index_together': [
                                    ('<colname>', ...),
                                    ...
                                ],
                                'indexes': [
                                    {
                                        'name': '<name>',
                                        'fields': ['<colname>', ...],
                                    },
                                    ...
                                ],
                                'pk_column': '<colname>',
                                'unique_together': [
                                    ('<colname>', ...),
                                    ...
                                ],
                                '__unique_together_applied': True|False,
                            },
                            'fields': {
                                'type': '<class_path>',
                                'related_model': '<app_label>.<class_name>',
                                'attrs': {
                                    '<field_attr_name>': <value>,
                                    ...
                                },
                            },
                        },
                        ...
                    },
                },
                ...
            },
        }
"""

from __future__ import unicode_literals

from copy import deepcopy
from importlib import import_module

from django.conf import global_settings
from django.core.exceptions import ImproperlyConfigured
from django.db import DEFAULT_DB_ALIAS, models
from django.utils.translation import ugettext as _

from django_evolution.compat import six
from django_evolution.compat.apps import get_apps, get_app
from django_evolution.compat.datastructures import OrderedDict
from django_evolution.compat.db import db_router_allows_schema_upgrade
from django_evolution.compat.models import (GenericRelation,
                                            get_models,
                                            get_remote_field,
                                            get_remote_field_model)
from django_evolution.consts import UpgradeMethod
from django_evolution.errors import (InvalidSignatureVersion,
                                     MissingSignatureError)
from django_evolution.utils.apps import get_app_label, get_legacy_app_label
from django_evolution.utils.evolutions import get_app_upgrade_info
from django_evolution.utils.migrations import MigrationList


#: The latest signature version.
LATEST_SIGNATURE_VERSION = 2


class BaseSignature(object):
    """Base class for a signature."""

    @classmethod
    def deserialize(self, sig_dict, sig_version, database=DEFAULT_DB_ALIAS):
        """Deserialize the signature.

        Args:
            sig_dict (dict):
                The dictionary containing signature data.

            sig_version (int):
                The stored signature version.

            database (unicode, optional):
                The name of the database.

        Returns:
            BaseSignature:
            The resulting signature class.

        Raises:
            django_evolution.errors.InvalidSignatureVersion:
                The signature version provided isn't supported.
        """
        raise NotImplementedError

    def diff(self, old_sig):
        """Diff against an older signature.

        The resulting data is dependent on the type of signature.

        Args:
            old_sig (BaseSignature):
                The old signature to diff against.

        Returns:
            object:
            The resulting diffed data.
        """
        raise NotImplementedError

    def clone(self):
        """Clone the signature.

        Returns:
            BaseSignature:
            The cloned signature.
        """
        raise NotImplementedError

    def serialize(self, sig_version=LATEST_SIGNATURE_VERSION):
        """Serialize data to a signature dictionary.

        Args:
            sig_version (int, optional):
                The signature version to serialize as. This always defaults
                to the latest.

        Returns:
            dict:
            The serialized data.

        Raises:
            django_evolution.errors.InvalidSignatureVersion:
                The signature version provided isn't supported.
        """
        raise NotImplementedError

    def __eq__(self, other):
        """Return whether two signatures are equal.

        Args:
            other (BaseSignature):
                The other signature.

        Returns:
            bool:
            ``True`` if the project signatures are equal. ``False`` if they
            are not.
        """
        raise NotImplementedError

    def __ne__(self, other):
        """Return whether two signatures are not equal.

        Args:
            other (BaseSignature):
                The other signature.

        Returns:
            bool:
            ``True`` if the project signatures are not equal. ``False`` if they
            are equal.
        """
        return not (self == other)

    def __repr__(self):
        """Return a string representation of the signature.

        Returns:
            unicode:
            A string representation of the signature.
        """
        raise NotImplementedError


class ProjectSignature(BaseSignature):
    """Signature information for a project.

    Projects are the top-level signature deserialized from and serialized to
    a :py:class:`~django_evolution.models.Version` model. They contain a
    signature version and information on all the applications tracked for the
    project.
    """

    @classmethod
    def from_database(cls, database):
        """Create a project signature from the database.

        This will look up all the applications registered in Django, turning
        each of them into a :py:class:`AppSignature` stored in this
        project signature.

        Args:
            database (unicode):
                The name of the database.

        Returns:
            ProjectSignature:
            The project signature based on the current application and
            database state.
        """
        project_sig = cls()

        for app in get_apps():
            project_sig.add_app(app, database)

        return project_sig

    @classmethod
    def deserialize(cls, project_sig_dict, database=DEFAULT_DB_ALIAS):
        """Deserialize a serialized project signature.

        Args:
            project_sig_dict (dict):
                The dictionary containing project signature data.

            database (unicode, optional):
                The name of the database.

        Returns:
            ProjectSignature:
            The resulting signature instance.

        Raises:
            django_evolution.errors.InvalidSignatureVersion:
                The signature version found in the dictionary is unsupported.
        """
        sig_version = project_sig_dict['__version__']
        validate_sig_version(sig_version)

        project_sig = cls()

        if sig_version == 2:
            app_sigs_dict = project_sig_dict['apps']
        elif sig_version == 1:
            app_sigs_dict = OrderedDict(
                (app_id, app_sig_dict)
                for app_id, app_sig_dict in six.iteritems(project_sig_dict)
                if app_id != '__version__'
            )

        for app_id, app_sig_dict in six.iteritems(app_sigs_dict):
            project_sig.add_app_sig(AppSignature.deserialize(
                app_id=app_id,
                app_sig_dict=app_sig_dict,
                sig_version=sig_version,
                database=database))

        return project_sig

    def __init__(self):
        """Initialize the signature."""
        self._app_sigs = OrderedDict()

    @property
    def app_sigs(self):
        """The application signatures in the project signature."""
        return six.itervalues(self._app_sigs)

    def add_app(self, app, database):
        """Add an application to the project signature.

        This will construct an :py:class:`AppSignature` and add it
        to the project signature.

        Args:
            app (module):
                The application module to create the signature from.

            database (unicode):
                The database name.
        """
        self.add_app_sig(AppSignature.from_app(app, database))

    def add_app_sig(self, app_sig):
        """Add an application signature to the project signature.

        Args:
            app_sig (AppSignature):
                The application signature to add.
        """
        self._app_sigs[app_sig.app_id] = app_sig

    def remove_app_sig(self, app_id):
        """Remove an application signature from the project signature.

        Args:
            app_id (unicode):
                The ID of the application signature to remove.

        Raises:
            django_evolution.errors.MissingSignatureError:
                The application ID does not represent a known application
                signature.
        """
        try:
            del self._app_sigs[app_id]
        except KeyError:
            raise MissingSignatureError(
                _('An application signature for "%s" could not be found.')
                % app_id)

    def get_app_sig(self, app_id, required=False):
        """Return an application signature with the given ID.

        Args:
            app_id (unicode):
                The ID of the application signature. This may be a modern
                app label, or a legacy app label.

            required (bool, optional):
                Whether the app signature must be present. If ``True`` and
                the signature is missing, this will raise an exception.

        Returns:
            AppSignature:
            The application signature, if found. If no application signature
            matches the ID, ``None`` will be returned.

        Raises:
            django_evolution.errors.MissingSignatureError:
                The application signature was not found, and ``required`` was
                ``True``.
        """
        app_sig = self._app_sigs.get(app_id)

        if app_sig is None:
            for temp_app_sig in six.itervalues(self._app_sigs):
                if temp_app_sig.legacy_app_label == app_id:
                    app_sig = temp_app_sig
                    break

        if app_sig is None and required:
            raise MissingSignatureError(
                _('Unable to find an application signature for "%s". '
                  'syncdb/migrate might need to be run first.')
                % (app_id,))

        return app_sig

    def diff(self, old_project_sig):
        """Diff against an older project signature.

        This will return a dictionary of changes between two project
        signatures.

        Args:
            old_project_sig (ProjectSignature):
                The old project signature to diff against.

        Returns:
            collections.OrderedDict:
            A dictionary in the following form::

                {
                    'changed': {
                        <app ID>: <AppSignature diff>,
                        ...
                    },
                    'deleted': [
                        <app ID>: [
                            <model name>,
                            ...
                        ],
                        ...
                    ],
                }

            Any key lacking a value will be ommitted from the diff.

        Raises:
            TypeError:
                The old signature provided was not a
                :py:class:`ProjectSignature`.
        """
        if not isinstance(old_project_sig, ProjectSignature):
            raise TypeError('Must provide a ProjectSignature to diff against, '
                            'not a %s.' % type(old_project_sig))

        changed_apps = OrderedDict()
        deleted_apps = OrderedDict()

        for old_app_sig in old_project_sig.app_sigs:
            new_app_sig = self.get_app_sig(old_app_sig.app_id)

            if new_app_sig:
                app_changes = new_app_sig.diff(old_app_sig)

                if app_changes:
                    # There are changes for this application. Store that
                    # in the diff.
                    changed_apps[new_app_sig.app_id] = app_changes
            else:
                # The application has been deleted.
                deleted_apps[old_app_sig.app_id] = [
                    model_sig.model_name
                    for model_sig in old_app_sig.model_sigs
                ]

        return OrderedDict(
            (key, value)
            for key, value in (('changed', changed_apps),
                               ('deleted', deleted_apps))
            if value
        )

    def clone(self):
        """Clone the signature.

        Returns:
            ProjectSignature:
            The cloned signature.
        """
        cloned_sig = ProjectSignature()

        for app_sig in self.app_sigs:
            cloned_sig.add_app_sig(app_sig.clone())

        return cloned_sig

    def serialize(self, sig_version=LATEST_SIGNATURE_VERSION):
        """Serialize project data to a signature dictionary.

        Args:
            sig_version (int, optional):
                The signature version to serialize as. This always defaults
                to the latest.

        Returns:
            dict:
            The serialized data.

        Raises:
            django_evolution.errors.InvalidSignatureVersion:
                The signature version provided isn't supported.
        """
        validate_sig_version(sig_version)

        project_sig_dict = {
            '__version__': sig_version,
        }

        if sig_version == 2:
            app_sigs_dict = OrderedDict()
            project_sig_dict['apps'] = app_sigs_dict
        elif sig_version == 1:
            app_sigs_dict = project_sig_dict

        for app_id, app_sig in six.iteritems(self._app_sigs):
            app_sigs_dict[app_id] = app_sig.serialize(sig_version)

        return project_sig_dict

    def __eq__(self, other):
        """Return whether two project signatures are equal.

        Args:
            other (ProjectSignature):
                The other project signature.

        Returns:
            bool:
            ``True`` if the project signatures are equal. ``False`` if they
            are not.
        """
        return (other is not None and
                dict.__eq__(self._app_sigs, other._app_sigs))

    def __repr__(self):
        """Return a string representation of the signature.

        Returns:
            unicode:
            A string representation of the signature.
        """
        return ('<ProjectSignature(apps=%r)>'
                % list(six.iterkeys(self._app_sigs)))


class AppSignature(BaseSignature):
    """Signature information for an application.

    Application signatures store information on a Django application and all
    models registered under that application.
    """

    @classmethod
    def from_app(cls, app, database):
        """Create an application signature from an application.

        This will store data on the application and create a
        :py:class:`ModelSignature` for each of the application's models.

        Args:
            app (module):
                The application module to create the signature from.

            database (unicode):
                The name of the database.

        Returns:
            AppSignature:
            The application signature based on the application.
        """
        app_label = get_app_label(app)
        app_upgrade_info = get_app_upgrade_info(app,
                                                simulate_applied=True,
                                                database=database)

        app_sig = cls(
            app_id=app_label,
            legacy_app_label=get_legacy_app_label(app),
            upgrade_method=app_upgrade_info.get('upgrade_method'),
            applied_migrations=app_upgrade_info.get('applied_migrations'))

        for model in get_models(app):
            if db_router_allows_schema_upgrade(database, app_label, model):
                app_sig.add_model(model)

        return app_sig

    @classmethod
    def deserialize(cls, app_id, app_sig_dict, sig_version,
                    database=DEFAULT_DB_ALIAS):
        """Deserialize a serialized application signature.

        Args:
            app_id (unicode):
                The application ID.

            app_sig_dict (dict):
                The dictionary containing application signature data.

            sig_version (int):
                The version of the serialized signature data.

            database (unicode, optional):
                The name of the database.

        Returns:
            AppSignature:
            The resulting signature instance.

        Raises:
            django_evolution.errors.InvalidSignatureVersion:
                The signature version provided isn't supported.
        """
        validate_sig_version(sig_version)

        legacy_app_label = None
        upgrade_method = None
        applied_migrations = None

        if sig_version == 2:
            model_sigs_dict = app_sig_dict['models']
            legacy_app_label = app_sig_dict['legacy_app_label']
            upgrade_method = app_sig_dict.get('upgrade_method')
            applied_migrations = app_sig_dict.get('applied_migrations')
        elif sig_version == 1:
            model_sigs_dict = app_sig_dict
            legacy_app_label = app_id

            # Try to figure out the upgrade method for this app, factoring in
            # just the presence of evolutions/migrations directories (*not*
            # scanning for any mutations that change the upgrade method).
            #
            # This might not find an upgrade method, which is okay. Other
            # heuristics during diffing will try to deal with unknown upgrade
            # methods, and when all else fails, explicit mutations can be
            # added to set the record straight.
            try:
                upgrade_info = get_app_upgrade_info(get_app(app_id),
                                                    scan_evolutions=False,
                                                    database=database)
                upgrade_method = upgrade_info.get('upgrade_method')
                applied_migrations = upgrade_info.get('applied_migrations')
            except ImproperlyConfigured:
                # An app with the ID couldn't be found. This is likely either
                # an issue with an app label change, a deleted app, or an
                # app that is dynamically added later.
                pass

        app_sig = cls(app_id=app_id,
                      legacy_app_label=legacy_app_label,
                      upgrade_method=upgrade_method,
                      applied_migrations=applied_migrations)
        app_sig._loaded_sig_version = sig_version

        for model_name, model_sig_dict in six.iteritems(model_sigs_dict):
            app_sig.add_model_sig(
                ModelSignature.deserialize(model_name=model_name,
                                           model_sig_dict=model_sig_dict,
                                           sig_version=sig_version,
                                           database=database))

        return app_sig

    def __init__(self, app_id, legacy_app_label=None, upgrade_method=None,
                 applied_migrations=None):
        """Initialize the signature.

        Args:
            app_id (unicode):
                The ID of the application. This will be the application label.
                On modern versions of Django, this may differ from the
                legacy app label.

            legacy_app_label (unicode, optional):
                The legacy label for the application. This is based on the
                module name.

            upgrade_method (unicode, optional):
                The upgrade method used for this application. This must be
                a value from
                :py:class:`~django_evolution.evolve.UpgradeMethod`, or
                ``None``.

            applied_migrations (set of unicode, optional):
                The migration names that are applied as of this signature.
        """
        self.app_id = app_id
        self.legacy_app_label = legacy_app_label or app_id
        self.upgrade_method = upgrade_method
        self.applied_migrations = applied_migrations

        self._loaded_sig_version = None
        self._model_sigs = OrderedDict()

    @property
    def model_sigs(self):
        """The model signatures stored on the application signature."""
        return six.itervalues(self._model_sigs)

    @property
    def applied_migrations(self):
        """The set of migration names applied to the app.

        Type:
            set of unicode
        """
        return self._applied_migrations

    @applied_migrations.setter
    def applied_migrations(self, value):
        """Set the migration names applied to the app.

        Args:
            value (set or list or
                   django_evolution.utils.migrations.MigratonList):
                The new migration names. This may be an explicit set/list
                of migration names, or it can be a MigrationList, of which
                only the migration names relevant to this app will be stored.
        """
        if isinstance(value, MigrationList):
            value = [
                info['name']
                for info in value
                if info['app_label'] == self.app_id
            ]

        if value is not None:
            value = set(value)

        self._applied_migrations = value

    def is_empty(self):
        """Return whether the application signature is empty.

        An empty application signature contains no models.

        Returns:
            bool:
            ``True`` if the signature is empty. ``False`` if it still has
            models in it.
        """
        return not bool(self._model_sigs)

    def add_model(self, model):
        """Add a model to the application signature.

        This will construct a :py:class:`ModelSignature` and add it to this
        application signature.

        Args:
            model (django.db.models.Model):
                The model to create the signature from.
        """
        self.add_model_sig(ModelSignature.from_model(model))

    def add_model_sig(self, model_sig):
        """Add a model signature to the application signature.

        Args:
            model_sig (ModelSignature):
                The model signature to add.
        """
        self._model_sigs[model_sig.model_name] = model_sig

    def remove_model_sig(self, model_name):
        """Remove a model signature from the application signature.

        Args:
            model_name (unicode):
                The name of the model.

        Raises:
            django_evolution.errors.MissingSignatureError:
                The model name does not represent a known model signature.
        """
        try:
            del self._model_sigs[model_name]
        except KeyError:
            raise MissingSignatureError(
                _('A model signature for "%s" could not be found.')
                % model_name)

    def clear_model_sigs(self):
        """Clear all model signatures from the application signature."""
        self._model_sigs.clear()

    def get_model_sig(self, model_name, required=False):
        """Return a model signature for the given model name.

        Args:
            model_name (unicode):
                The name of the model.

            required (bool, optional):
                Whether the model signature must be present. If ``True`` and
                the signature is missing, this will raise an exception.

        Returns:
            ModelSignature:
            The model signature, if found. If no model signature matches
            the model name, ``None`` will be returned.

        Raises:
            django_evolution.errors.MissingSignatureError:
                The model signature was not found, and ``required`` was
                ``True``.
        """
        model_sig = self._model_sigs.get(model_name)

        if model_sig is None and required:
            raise MissingSignatureError(
                _('Unable to find a model signature for "%s.%s". '
                  'syncdb/migrate might need to be run first.')
                % (self.app_id, model_name))

        return model_sig

    def diff(self, old_app_sig):
        """Diff against an older application signature.

        This will return a dictionary containing the differences between
        two application signatures.

        Args:
            old_app_sig (AppSignature):
                The old app signature to diff against.

        Returns:
            collections.OrderedDict:
            A dictionary in the following form::

                {
                    'changed': {
                        '<model_name>': <ModelSignature diff>,
                        ...
                    },
                    'deleted': [ <list of deleted model names> ],
                    'meta_changed': {
                        '<prop_name>': {
                            'old': <old value>,
                            'new': <new value>,
                        },
                        ...
                    }
                }

            Any key lacking a value will be ommitted from the diff.

        Raises:
            TypeError:
                The old signature provided was not an :py:class:`AppSignature`.
        """
        if not isinstance(old_app_sig, AppSignature):
            raise TypeError('Must provide an AppSignature to diff against, '
                            'not a %s.' % type(old_app_sig))

        deleted_models = []
        changed_models = OrderedDict()
        meta_changed = OrderedDict()

        # Process the models in the application, looking for changes to
        # fields and meta attributes.
        for old_model_sig in old_app_sig.model_sigs:
            model_name = old_model_sig.model_name
            new_model_sig = self.get_model_sig(model_name)

            if new_model_sig:
                model_changes = new_model_sig.diff(old_model_sig)

                if model_changes:
                    # There are changes for this model. Store that in the
                    # diff.
                    changed_models[model_name] = model_changes
            else:
                # The model has been deleted.
                deleted_models.append(model_name)

        # Check for changes to basic metadata for the app.
        for key in ('app_id', 'legacy_app_label'):
            old_value = getattr(old_app_sig, key)
            new_value = getattr(self, key)

            if old_value != new_value:
                meta_changed[key] = {
                    'old': old_value,
                    'new': new_value,
                }

        # Check if the upgrade method has changed. We have to do this a bit
        # carefully, as the old value might be None, due to:
        #
        # 1. Coming from a version 1 signature (meaning that we only care if
        #    there are actual changes to the app and we're also transitioning
        #    to Migrations)
        #
        # 2. Coming from a version 2 signature (including a database scan)
        #    and the old signature doesn't list an upgrade method for the
        #    app (meaning it likely didn't use either evolutions or
        #    migrations).
        old_upgrade_method = old_app_sig.upgrade_method
        new_upgrade_method = self.upgrade_method
        old_sig_version = old_app_sig._loaded_sig_version

        if (old_upgrade_method != new_upgrade_method and
            ((old_sig_version is None and
              old_upgrade_method is not None) or
             (old_sig_version == 1 and
              (changed_models or deleted_models) and
              old_upgrade_method is None and
              new_upgrade_method != UpgradeMethod.EVOLUTIONS))):
            # The upgrade method has changed. If we're moving to migrations,
            # discard any other changes to the model. We're working with the
            # assumption that the migrations will account for any changes.
            #
            # The assumption may technically be wrong (there may be
            # evolutions to apply before migrations takes over), but we can't
            # easily separate out the changes made by each method. However,
            # since we've recorded a change to this app, the evolver will
            # still apply any remaining evolutions, so we're covered.
            meta_changed['upgrade_method'] = {
                'old': old_upgrade_method,
                'new': new_upgrade_method,
            }

        if new_upgrade_method == UpgradeMethod.MIGRATIONS:
            # If we're using migrations, we don't want to show any other
            # changes to the models. Those are handled by migrations, and
            # aren't something we want to include in the diff, since they
            # can't be resolved by evolutions.
            changed_models.clear()
            deleted_models = []

        # Build the dictionary of changes for the app.
        return OrderedDict(
            (key, value)
            for key, value in (('changed', changed_models),
                               ('deleted', deleted_models),
                               ('meta_changed', meta_changed))
            if value
        )

    def clone(self):
        """Clone the signature.

        Returns:
            AppSignature:
            The cloned signature.
        """
        cloned_sig = AppSignature(
            app_id=self.app_id,
            legacy_app_label=self.legacy_app_label,
            upgrade_method=self.upgrade_method,
            applied_migrations=deepcopy(self.applied_migrations))

        for model_sig in self.model_sigs:
            cloned_sig.add_model_sig(model_sig.clone())

        return cloned_sig

    def serialize(self, sig_version=LATEST_SIGNATURE_VERSION):
        """Serialize application data to a signature dictionary.

        Args:
            sig_version (int, optional):
                The signature version to serialize as. This always defaults
                to the latest.

        Returns:
            dict:
            The serialized data.

        Raises:
            django_evolution.errors.InvalidSignatureVersion:
                The signature version provided isn't supported.
        """
        validate_sig_version(sig_version)

        app_sig_dict = OrderedDict()

        if sig_version == 2:
            app_sig_dict['legacy_app_label'] = self.legacy_app_label

            if self.upgrade_method:
                app_sig_dict['upgrade_method'] = self.upgrade_method

                if self.upgrade_method == UpgradeMethod.MIGRATIONS:
                    app_sig_dict['applied_migrations'] = \
                        sorted(self.applied_migrations or [])

            # Add an ordered dictionary of models to the signature.
            model_sigs_dict = OrderedDict()
            app_sig_dict['models'] = model_sigs_dict
        elif sig_version == 1:
            model_sigs_dict = app_sig_dict

        for model_name, model_sig in six.iteritems(self._model_sigs):
            model_sigs_dict[model_name] = model_sig.serialize(sig_version)

        return app_sig_dict

    def __eq__(self, other):
        """Return whether two application signatures are equal.

        Args:
            other (AppSignature):
                The other application signature.

        Returns:
            bool:
            ``True`` if the application signatures are equal. ``False`` if
            they are not.
        """
        return (other is not None and
                self.app_id == other.app_id and
                self.legacy_app_label == other.legacy_app_label and
                self.upgrade_method == other.upgrade_method and
                self.applied_migrations == other.applied_migrations and
                dict.__eq__(self._model_sigs, other._model_sigs))

    def __repr__(self):
        """Return a string representation of the signature.

        Returns:
            unicode:
            A string representation of the signature.
        """
        return ('<AppSignature(app_id=%r, legacy_app_label=%r,'
                ' upgrade_method=%r, models=%r)>'
                % (self.app_id, self.legacy_app_label, self.upgrade_method,
                   list(six.iterkeys(self._model_sigs))))


class ModelSignature(BaseSignature):
    """Signature information for a model.

    Model signatures store information on the model and include signatures for
    its fields and ``_meta`` attributes.
    """

    @classmethod
    def from_model(cls, model):
        """Create a model signature from a model.

        This will store data on the model and its ``_meta`` attributes, and
        create a :py:class:`FieldSignature` for each field.

        Args:
            model (django.db.models.Model):
                The model to create a signature from.

        Returns:
            ModelSignature:
            The signature based on the model.
        """
        meta = model._meta
        model_sig = cls(db_tablespace=meta.db_tablespace,
                        index_together=deepcopy(meta.index_together),
                        model_name=meta.object_name,
                        pk_column=six.text_type(meta.pk.column),
                        table_name=meta.db_table,
                        unique_together=deepcopy(meta.unique_together))
        model_sig._unique_together_applied = True

        if getattr(meta, 'constraints', None):
            # Django >= 2.2
            for constraint in meta.original_attrs['constraints']:
                model_sig.add_constraint(constraint)

        if getattr(meta, 'indexes', None):
            # Django >= 1.11
            for index in meta.original_attrs['indexes']:
                model_sig.add_index(index)

        for field in meta.local_fields + meta.local_many_to_many:
            # Don't generate a signature for generic relations.
            if not isinstance(field, GenericRelation):
                model_sig.add_field(field)

        return model_sig

    @classmethod
    def deserialize(cls, model_name, model_sig_dict, sig_version,
                    database=DEFAULT_DB_ALIAS):
        """Deserialize a serialized model signature.

        Args:
            model_name (unicode):
                The model name.

            model_sig_dict (dict):
                The dictionary containing model signature data.

            sig_version (int):
                The version of the serialized signature data.

            database (unicode, optional):
                The name of the database.

        Returns:
            ModelSignature:
            The resulting signature instance.

        Raises:
            django_evolution.errors.InvalidSignatureVersion:
                The signature version provided isn't supported.
        """
        validate_sig_version(sig_version)

        meta_sig_dict = model_sig_dict['meta']
        fields_sig_dict = model_sig_dict['fields']

        model_sig = cls(
            db_tablespace=meta_sig_dict.get('db_tablespace'),
            index_together=meta_sig_dict.get('index_together', []),
            model_name=model_name,
            pk_column=meta_sig_dict.get('pk_column'),
            table_name=meta_sig_dict.get('db_table'),
            unique_together=meta_sig_dict.get('unique_together', []))
        model_sig._unique_together_applied = \
            meta_sig_dict.get('__unique_together_applied', False)

        # Django >= 2.2
        for constraint_sig_dict in meta_sig_dict.get('constraints', []):
            model_sig.add_constraint_sig(
                ConstraintSignature.deserialize(
                    constraint_sig_dict=constraint_sig_dict,
                    sig_version=sig_version,
                    database=database))

        # Django >= 1.11
        for index_sig_dict in meta_sig_dict.get('indexes', []):
            model_sig.add_index_sig(
                IndexSignature.deserialize(index_sig_dict=index_sig_dict,
                                           sig_version=sig_version,
                                           database=database))

        for field_name, field_sig_dict in six.iteritems(fields_sig_dict):
            model_sig.add_field_sig(
                FieldSignature.deserialize(field_name=field_name,
                                           field_sig_dict=field_sig_dict,
                                           sig_version=sig_version,
                                           database=database))

        return model_sig

    def __init__(self, model_name, table_name, db_tablespace=None,
                 index_together=[], pk_column=None, unique_together=[]):
        """Initialize the signature.

        Args:
            model_name (unicode):
                The name of the model.

            table_name (unicode):
                The name of the table in the database.

            db_tablespace (unicode, optional):
                The tablespace for the model. This is database-specific.

            index_together (list of tuple, optional):
                A list of fields that are indexed together.

            pk_column (unicode, optional):
                The column for the primary key.

            unique_together (list of tuple, optional):
                The list of fields that are unique together.
        """
        self.model_name = model_name
        self.db_tablespace = db_tablespace
        self.table_name = table_name
        self.index_together = self._normalize_together(index_together)
        self.pk_column = pk_column
        self.unique_together = self._normalize_together(unique_together)

        self.constraint_sigs = []
        self.index_sigs = []
        self._field_sigs = OrderedDict()
        self._unique_together_applied = False

    @property
    def field_sigs(self):
        """The field signatures on the model signature."""
        return six.itervalues(self._field_sigs)

    def add_field(self, field):
        """Add a field to the model signature.

        This will construct a :py:class:`FieldSignature` and add it to this
        model signature.

        Args:
            field (django.db.models.Field):
                The field to create the signature from.
        """
        self.add_field_sig(FieldSignature.from_field(field))

    def add_field_sig(self, field_sig):
        """Add a field signature to the model signature.

        Args:
            field_sig (FieldSignature):
                The field signature to add.
        """
        self._field_sigs[field_sig.field_name] = field_sig

    def remove_field_sig(self, field_name):
        """Remove a field signature from the model signature.

        Args:
            field_name (unicode):
                The name of the field.

        Raises:
            django_evolution.errors.MissingSignatureError:
                The field name does not represent a known field signature.
        """
        try:
            del self._field_sigs[field_name]
        except KeyError:
            raise MissingSignatureError(
                _('A field signature for "%s" could not be found.')
                % field_name)

    def get_field_sig(self, field_name, required=False):
        """Return a field signature for the given field name.

        Args:
            field_name (unicode):
                The name of the field.

            required (bool, optional):
                Whether the model signature must be present. If ``True`` and
                the signature is missing, this will raise an exception.

        Returns:
            FieldSignature:
            The field signature, if found. If no field signature matches
            the field name, ``None`` will be returned.

        Raises:
            django_evolution.errors.MissingSignatureError:
                The model signature was not found, and ``required`` was
                ``True``.
        """
        field_sig = self._field_sigs.get(field_name)

        if field_sig is None and required:
            raise MissingSignatureError(
                _('Unable to find a field signature for "%s.%s". '
                  'syncdb/migrate might need to be run first.')
                % (self.model_name, field_name))

        return field_sig

    def add_constraint(self, constraint):
        """Add an explicit constraint to the models.

        This is only used on Django 2.2 or higher. It corresponds to the
        :py:attr:`model._meta.constraints
        <django.db.models.Options.constraints` attribute.

        Args:
            constraint (django.db.models.BaseConstraint):
                The constraint to add.
        """
        self.add_constraint_sig(
            ConstraintSignature.from_constraint(constraint))

    def add_constraint_sig(self, constraint_sig):
        """Add an explicit constraint signature to the models.

        This is only used on Django 2.2 or higher. It corresponds to the
        :py:attr:`model._meta.constraints
        <django.db.models.Options.constraints` attribute.

        Args:
            constraint_sig (ConstraintSignature):
                The constraint signature to add.
        """
        self.constraint_sigs.append(constraint_sig)

    def add_index(self, index):
        """Add an explicit index to the models.

        This is only used on Django 1.11 or higher. It corresponds to the
        :py:attr:`model._meta.indexes <django.db.models.Options.indexes`
        attribute.

        Args:
            index (django.db.models.Index):
                The index to add.
        """
        self.add_index_sig(IndexSignature.from_index(index))

    def add_index_sig(self, index_sig):
        """Add an explicit index signature to the models.

        This is only used on Django 1.11 or higher. It corresponds to the
        :py:attr:`model._meta.indexes <django.db.models.Options.indexes`
        attribute.

        Args:
            index_sig (IndexSignature):
                The index signature to add.
        """
        self.index_sigs.append(index_sig)

    def has_unique_together_changed(self, old_model_sig):
        """Return whether unique_together has changed between signatures.

        ``unique_together`` is considered to have changed under the following
        conditions:

        * They are different in value.
        * Either the old or new is non-empty (even if equal) and evolving
          from an older signature from Django Evolution pre-0.7, where
          unique_together wasn't applied to the database.

        Args:
            old_model_sig (ModelSignature):
                The old model signature to compare against.

        Return:
            bool:
            ``True`` if the value has changed. ``False`` if they're
            considered equal for the purposes of evolution.
        """
        old_unique_together = old_model_sig.unique_together
        new_unique_together = self.unique_together

        return (old_unique_together != new_unique_together or
                ((old_unique_together or new_unique_together) and
                 not old_model_sig._unique_together_applied))

    def diff(self, old_model_sig):
        """Diff against an older model signature.

        This will return a dictionary containing the differences in fields
        and meta information between two signatures.

        Args:
            old_model_sig (ModelSignature):
                The old model signature to diff against.

        Returns:
            collections.OrderedDict:
            A dictionary in the following form::

                {
                    'added': [
                        <field name>,
                        ...
                    ],
                    'deleted': [
                        <field name>,
                        ...
                    ],
                    'changed': {
                        <field name>: <FieldSignature diff>,
                        ...
                    },
                    'meta_changed': [
                        <'constraints'>,
                        <'indexes'>,
                        <'index_together'>,
                        <'unique_together'>,
                    ],
                }

            Any key lacking a value will be ommitted from the diff.

        Raises:
            TypeError:
                The old signature provided was not a
                :py:class:`ModelSignature`.
        """
        if not isinstance(old_model_sig, ModelSignature):
            raise TypeError('Must provide a ModelSignature to diff against, '
                            'not a %s.' % type(old_model_sig))

        # Go through all the fields, looking for changed and deleted fields.
        changed_fields = OrderedDict()
        deleted_fields = []

        for old_field_sig in old_model_sig.field_sigs:
            field_name = old_field_sig.field_name
            new_field_sig = self.get_field_sig(field_name)

            if new_field_sig:
                # Go through all the attributes on the field, looking for
                # changes.
                changed_field_attrs = new_field_sig.diff(old_field_sig)

                if changed_field_attrs:
                    # There were attribute changes. Store those with the field.
                    changed_fields[field_name] = changed_field_attrs
            else:
                # The field has been deleted.
                deleted_fields.append(field_name)

        # Go through the list of added fields and add any that don't
        # exist in the original field list.
        added_fields = [
            field_sig.field_name
            for field_sig in self.field_sigs
            if not old_model_sig.get_field_sig(field_sig.field_name)
        ]

        # Build a list of changes to Model.Meta attributes.
        meta_changed = []

        if self.has_unique_together_changed(old_model_sig):
            meta_changed.append('unique_together')

        if self.index_together != old_model_sig.index_together:
            meta_changed.append('index_together')

        if list(self.index_sigs) != list(old_model_sig.index_sigs):
            meta_changed.append('indexes')

        if list(self.constraint_sigs) != list(old_model_sig.constraint_sigs):
            meta_changed.append('constraints')

        return OrderedDict(
            (key, value)
            for key, value in (('added', added_fields),
                               ('changed', changed_fields),
                               ('deleted', deleted_fields),
                               ('meta_changed', meta_changed))
            if value
        )

    def clone(self):
        """Clone the signature.

        Returns:
            ModelSignature:
            The cloned signature.
        """
        cloned_sig = ModelSignature(
            model_name=self.model_name,
            table_name=self.table_name,
            db_tablespace=self.db_tablespace,
            index_together=deepcopy(self.index_together),
            pk_column=self.pk_column,
            unique_together=deepcopy(self.unique_together))
        cloned_sig._unique_together_applied = self._unique_together_applied

        for field_sig in self.field_sigs:
            cloned_sig.add_field_sig(field_sig.clone())

        for constraint_sig in self.constraint_sigs:
            cloned_sig.add_constraint_sig(constraint_sig.clone())

        for index_sig in self.index_sigs:
            cloned_sig.add_index_sig(index_sig.clone())

        return cloned_sig

    def serialize(self, sig_version=LATEST_SIGNATURE_VERSION):
        """Serialize model data to a signature dictionary.

        Args:
            sig_version (int, optional):
                The signature version to serialize as. This always defaults
                to the latest.

        Returns:
            dict:
            The serialized data.

        Raises:
            django_evolution.errors.InvalidSignatureVersion:
                The signature version provided isn't supported.
        """
        validate_sig_version(sig_version)

        return {
            'meta': {
                'constraints': [
                    constraint_sig.serialize(sig_version)
                    for constraint_sig in self.constraint_sigs
                ],
                'db_table': self.table_name,
                'db_tablespace': self.db_tablespace,
                'index_together': self.index_together,
                'indexes': [
                    index_sig.serialize(sig_version)
                    for index_sig in self.index_sigs
                ],
                'pk_column': self.pk_column,
                'unique_together': self.unique_together,
                '__unique_together_applied': self._unique_together_applied,
            },
            'fields': OrderedDict(
                (field_name, field_sig.serialize(sig_version))
                for field_name, field_sig in six.iteritems(self._field_sigs)
            ),
        }

    def __eq__(self, other):
        """Return whether two model signatures are equal.

        Args:
            other (ModelSignature):
                The other model signature.

        Returns:
            bool:
            ``True`` if the model signatures are equal. ``False`` if they
            are not.
        """
        return (other is not None and
                self.table_name == other.table_name and
                self.db_tablespace == other.db_tablespace and
                set(self.constraint_sigs) == set(other.constraint_sigs) and
                set(self.index_sigs) == set(other.index_sigs) and
                (set(self._normalize_together(self.index_together)) ==
                 set(self._normalize_together(other.index_together))) and
                self.model_name == other.model_name and
                self.pk_column == other.pk_column and
                dict.__eq__(self._field_sigs, other._field_sigs) and
                not self.has_unique_together_changed(other))

    def __repr__(self):
        """Return a string representation of the signature.

        Returns:
            unicode:
            A string representation of the signature.
        """
        return '<ModelSignature(model_name=%r)>' % self.model_name

    def _normalize_together(self, together):
        """Normalize a <field>_together value.

        This is intended to normalize ``index_together`` and
        ``unique_together`` values so that they're reliably stored in a
        consistent format.

        Args:
            together (object):
                The value to normalize.

        Returns:
            list of tuple:
            The normalized value.
        """
        if not together:
            return []

        if not isinstance(together[0], (tuple, list)):
            together = (together,)

        return [
            tuple(item)
            for item in together
        ]


class ConstraintSignature(BaseSignature):
    """Signature information for a explicit constraint.

    These indexes were introduced in Django 1.11. They correspond to entries
    in the :py:attr:`model._meta.indexes <django.db.models.Options.indexes`
    attribute.

    Constraint signatures store information on a constraint on model,
    including the constraint name, type, and any attribute values needed for
    constructing the constraint.
    """

    @classmethod
    def from_constraint(cls, constraint):
        """Create a constraint signature from a field.

        Args:
            constraint (django.db.models.BaseConstraint):
                The constraint to create a signature from.

        Returns:
            ConstraintSignature:
            The signature based on the constraint.
        """
        attrs = constraint.deconstruct()[2]
        del attrs['name']

        return cls(name=constraint.name,
                   constraint_type=type(constraint),
                   attrs=attrs)

    @classmethod
    def deserialize(cls, constraint_sig_dict, sig_version,
                    database=DEFAULT_DB_ALIAS):
        """Deserialize a serialized constraint signature.

        Args:
            constraint_sig_dict (dict):
                The dictionary containing constraint signature data.

            sig_version (int):
                The version of the serialized signature data.

            database (unicode, optional):
                The name of the database.

        Returns:
            ConstraintSignature:
            The resulting signature instance.

        Raises:
            django_evolution.errors.InvalidSignatureVersion:
                The signature version provided isn't supported.
        """
        validate_sig_version(sig_version)

        type_module, type_name = constraint_sig_dict['type'].rsplit('.', 1)

        try:
            constraint_type = getattr(import_module(type_module), type_name)
        except (AttributeError, ImportError):
            raise ImportError('Unable to locate constraint type %s'
                              % '%s.%s' % (type_module, type_name))

        attrs = {
            key: cls._deserialize_attr_value(attr_value)
            for key, attr_value in six.iteritems(constraint_sig_dict['attrs'])
        }

        return cls(name=constraint_sig_dict['name'],
                   constraint_type=constraint_type,
                   attrs=attrs)

    @classmethod
    def _deserialize_attr_value(cls, sig_value):
        """Return an attribute value from serialized data.

        This will take care to re-construct any deconstructed data that's
        stored in the signature for arguments passed to the constraint class.

        Args:
            sig_value (object):
                The value in the signature to deserialize.

        Returns:
            object:
            The deserialized value.
        """
        if (isinstance(sig_value, dict) and
            sig_value.get('_deconstructed') is True):
            attr_cls_path = sig_value['type']
            attr_cls_module, attr_cls_name = attr_cls_path.rsplit('.', 1)

            try:
                attr_cls = getattr(import_module(attr_cls_module),
                                   attr_cls_name)
            except (AttributeError, ImportError):
                raise ImportError('Unable to locate constraint attribute '
                                  'value type %s'
                                  % attr_cls_path)

            args = tuple(
                cls._deserialize_attr_value(arg_value)
                for arg_value in sig_value['args']
            )

            kwargs = {
                key: cls._deserialize_attr_value(arg_value)
                for key, arg_value in six.iteritems(sig_value['kwargs'])
            }

            # Let any exception bubble up.
            value = attr_cls(*args, **kwargs)
        else:
            value = sig_value

        return value

    def __init__(self, name, constraint_type, attrs=None):
        """Initialize the signature.

        Args:
            name (unicode):
                The name of the constraint.

            constraint_type (cls):
                The class for the constraint. This would be a subclass of
                :py:class:`django.db.models.BaseConstraint`.

            attrs (dict, optional):
                Attributes to pass when constructing the constraint.
        """
        self.name = name
        self.type = constraint_type
        self.attrs = attrs

    def clone(self):
        """Clone the signature.

        Returns:
            ConstraintSignature:
            The cloned signature.
        """
        return ConstraintSignature(name=self.name,
                                   constraint_type=self.type,
                                   attrs=deepcopy(self.attrs))

    def serialize(self, sig_version=LATEST_SIGNATURE_VERSION):
        """Serialize constraint data to a signature dictionary.

        Args:
            sig_version (int, optional):
                The signature version to serialize as. This always defaults
                to the latest.

        Returns:
            dict:
            The serialized data.

        Raises:
            django_evolution.errors.InvalidSignatureVersion:
                The signature version provided isn't supported.
        """
        validate_sig_version(sig_version)

        type_module = self.type.__module__

        if type_module.startswith('django.db.models.constraints'):
            type_module = 'django.db.models'

        attrs = {}

        for key, value in six.iteritems(self.attrs):
            if hasattr(value, 'deconstruct'):
                attr_type_path, attr_args, attr_kwargs = value.deconstruct()

                value = {
                    'type': attr_type_path,
                    'args': attr_args,
                    'kwargs': attr_kwargs,
                    '_deconstructed': True,
                }

            attrs[key] = value

        return {
            'name': self.name,
            'type': '%s.%s' % (type_module, self.type.__name__),
            'attrs': attrs,
        }

    def __eq__(self, other):
        """Return whether two constraint signatures are equal.

        Args:
            other (ConstraintSignature):
                The other constraint signature.

        Returns:
            bool:
            ``True`` if the constraint signatures are equal. ``False`` if they
            are not.
        """
        return (other is not None and
                self.name == other.name and
                self.type is other.type and
                dict.__eq__(self.attrs, other.attrs))

    def __hash__(self):
        """Return a hash of the signature.

        This is required for comparison within a :py:class:`set`.

        Returns:
            int:
            The hash of the signature.
        """
        return hash(repr(self))

    def __repr__(self):
        """Return a string representation of the signature.

        Returns:
            unicode:
            A string representation of the signature.
        """
        return ('<ConstraintSignature(name=%r, type=%r, attrs=%r)>'
                % (self.name, self.type, self.attrs))

    def _serialize_attr_value(self, value):
        """Return a serialized version of a constraint attribute value.

        If the value has a ``deconstruct`` method, then this will call it
        and provide a serialized form of the results, allowing the object
        to be re-constructed properly when the signature is deserialized.

        Args:
            value (object):
                The value to serialize.

        Returns:
            object:
            The serialized value.
        """
        if hasattr(value, 'deconstruct'):
            assert callable(value.deconstruct)

            attr_type_path, attr_args, attr_kwargs = value.deconstruct()

            value = {
                'type': attr_type_path,
                'args': [
                    self._deconstruct_attr_value(arg_value)
                    for arg_value in attr_args
                ],
                'kwargs': {
                    key: self._deconstruct_attr_value(arg_value)
                    for key, arg_value in attr_kwargs
                },
                '_deconstructed': True,
            }

        return value


class IndexSignature(BaseSignature):
    """Signature information for an explicit index.

    These indexes were introduced in Django 1.11. They correspond to entries
    in the :py:attr:`model._meta.indexes <django.db.models.Options.indexes`
    attribute.
    """

    @classmethod
    def from_index(cls, index):
        """Create an index signature from an index.

        Args:
            index (django.db.models.Index):
                The index to create the signature from.

        Returns:
            IndexSignature:
            The signature based on the index.
        """
        return cls(name=index.name or None,
                   fields=index.fields)

    @classmethod
    def deserialize(cls, index_sig_dict, sig_version,
                    database=DEFAULT_DB_ALIAS):
        """Deserialize a serialized index signature.

        Args:
            index_sig_dict (dict):
                The dictionary containing index signature data.

            sig_version (int):
                The version of the serialized signature data.

            database (unicode, optional):
                The name of the database.

        Returns:
            IndexSignature:
            The resulting signature instance.

        Raises:
            django_evolution.errors.InvalidSignatureVersion:
                The signature version provided isn't supported.
        """
        validate_sig_version(sig_version)

        return cls(name=index_sig_dict.get('name'),
                   fields=index_sig_dict['fields'])

    def __init__(self, fields, name=None):
        """Initialize the signature.

        Args:
            fields (list of unicode):
                The list of field names the index is comprised of.

            name (unicode, optional):
                The optional name of the index.

        """
        self.fields = fields
        self.name = name

    def clone(self):
        """Clone the signature.

        Returns:
            IndexSignature:
            The cloned signature.
        """
        return IndexSignature(name=self.name,
                              fields=list(self.fields))

    def serialize(self, sig_version=LATEST_SIGNATURE_VERSION):
        """Serialize index data to a signature dictionary.

        Args:
            sig_version (int, optional):
                The signature version to serialize as. This always defaults
                to the latest.

        Returns:
            dict:
            The serialized data.

        Raises:
            django_evolution.errors.InvalidSignatureVersion:
                The signature version provided isn't supported.
        """
        validate_sig_version(sig_version)

        index_sig_dict = {
            'fields': self.fields,
        }

        if self.name:
            index_sig_dict['name'] = self.name

        return index_sig_dict

    def __eq__(self, other):
        """Return whether two index signatures are equal.

        Args:
            other (IndexSignature):
                The other index signature.

        Returns:
            bool:
            ``True`` if the index signatures are equal. ``False`` if they
            are not.
        """
        return (other is not None and
                ((not self.name and not other.name) or
                 self.name == other.name) and
                self.fields == other.fields)

    def __hash__(self):
        """Return a hash of the signature.

        This is required for comparison within a :py:class:`set`.

        Returns:
            int:
            The hash of the signature.
        """
        return hash(repr(self))

    def __repr__(self):
        """Return a string representation of the signature.

        Returns:
            unicode:
            A string representation of the signature.
        """
        return '<IndexSignature(name=%r, fields=%r)>' % (self.name,
                                                         self.fields)


class FieldSignature(BaseSignature):
    """Signature information for a field.

    Field signatures store information on a field on model, including the
    field name, type, and any attribute values needed for migrating the
    schema.
    """

    _ATTRIBUTE_DEFAULTS = {
        '*': {
            'primary_key': False,
            'max_length': None,
            'unique': False,
            'null': False,
            'db_index': False,
            'db_column': None,
            'db_tablespace': global_settings.DEFAULT_TABLESPACE,
        },
        models.DecimalField: {
            'max_digits': None,
            'decimal_places': None,
        },
        models.ForeignKey: {
            'db_index': True,
        },
        models.ManyToManyField: {
            'db_table': None,
        },
        models.OneToOneField: {
            'db_index': True,
        },
    }

    _ATTRIBUTE_ALIASES = {
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

    @classmethod
    def from_field(cls, field):
        """Create a field signature from a field.

        Args:
            field (django.db.models.Field):
                The field to create a signature from.

        Returns:
            FieldSignature:
            The signature based on the field.
        """
        field_type = type(field)
        field_attrs = {}

        defaults = cls._get_defaults_for_field_type(field_type)

        for attr, default in six.iteritems(defaults):
            alias = cls._ATTRIBUTE_ALIASES.get(attr)

            if alias and hasattr(field, alias):
                value = getattr(field, alias)
            elif hasattr(field, attr):
                value = getattr(field, attr)
            else:
                continue

            if value != default:
                field_attrs[attr] = value

        remote_field = get_remote_field(field)

        if remote_field:
            remote_field_meta = get_remote_field_model(remote_field)._meta

            related_model = '%s.%s' % (
                remote_field_meta.app_label,
                remote_field_meta.object_name,
            )
        else:
            related_model = None

        return cls(field_name=field.name,
                   field_type=field_type,
                   field_attrs=field_attrs,
                   related_model=related_model)

    @classmethod
    def deserialize(cls, field_name, field_sig_dict, sig_version,
                    database=DEFAULT_DB_ALIAS):
        """Deserialize a serialized field signature.

        Args:
            field_name (unicode):
                The name of the field.

            field_sig_dict (dict):
                The dictionary containing field signature data.

            sig_version (int):
                The version of the serialized signature data.

            database (unicode, optional):
                The name of the database.

        Returns:
            FieldSignature:
            The resulting signature instance.

        Raises:
            django_evolution.errors.InvalidSignatureVersion:
                The signature version provided isn't supported.
        """
        validate_sig_version(sig_version)

        if sig_version == 2:
            field_sig_attrs = field_sig_dict.get('attrs', {})

            # Load the class for the referenced field type.
            field_type_module, field_type_name = \
                field_sig_dict['type'].rsplit('.', 1)

            # If we have a field path in the signature that lives in
            # django.db.models.fields, update it to look in django.db.models
            # instead. This is for compatibility across all Django versions.
            if field_type_module.startswith('django.db.models.fields'):
                field_type_module = 'django.db.models'

            try:
                field_type = getattr(import_module(field_type_module),
                                     field_type_name)
            except (AttributeError, ImportError):
                raise ImportError('Unable to locate field type %s'
                                  % '%s.%s' % (field_type_module,
                                               field_type_name))
        elif sig_version == 1:
            field_sig_attrs = field_sig_dict
            field_type = field_sig_dict['field_type']

        field_attrs = {}

        for attr in cls._iter_attrs_for_field_type(field_type):
            if hasattr(cls, attr):
                # This is stored on the field signature class itself, so
                # it's not attribute data we want to load.
                continue

            alias = cls._ATTRIBUTE_ALIASES.get(attr)

            if alias and alias in field_sig_attrs:
                value = field_sig_attrs[alias]
            elif attr in field_sig_attrs:
                value = field_sig_attrs[attr]
            else:
                # The signature didn't contain a value for this attribute.
                continue

            field_attrs[attr] = value

        return cls(field_name=field_name,
                   field_type=field_type,
                   field_attrs=field_attrs,
                   related_model=field_sig_dict.get('related_model'))

    @classmethod
    def _iter_attrs_for_field_type(cls, field_type):
        """Iterate through attribute names for a field type.

        The attributes returned are those that impact the schema for a field's
        column.

        Args:
            field_type (type):
                The class for the field. This would be a subclass of
                :py:class:`django.db.models.Field`.

        Yield:
            unicode:
            An attribute for a field type.
        """
        return six.iterkeys(cls._get_defaults_for_field_type(field_type))

    @classmethod
    def _get_defaults_for_field_type(cls, field_type):
        """Return attribute names and defaults for a field type.

        The attributes returned are those that impact the schema for a field's
        column.

        Args:
            field_type (type):
                The class for the field. This would be a subclass of
                :py:class:`django.db.models.Field`.

        Returns:
            dict:
            The dictionary of attribute names and values.
        """
        defaults = cls._ATTRIBUTE_DEFAULTS['*'].copy()
        defaults.update(cls._ATTRIBUTE_DEFAULTS.get(field_type, {}))

        return defaults

    def __init__(self, field_name, field_type, field_attrs=None,
                 related_model=None):
        """Initialize the signature.

        Args:
            field_name (unicode):
                The name of the field.

            field_type (cls):
                The class for the field. This would be a subclass of
                :py:class:`django.db.models.Field`.

            field_attrs (dict, optional):
                Attributes to set on the field.

            related_model (unicode, optional):
                The full path to a related model.
        """
        self.field_name = field_name
        self.field_type = field_type
        self.field_attrs = field_attrs or OrderedDict()
        self.related_model = related_model

    def get_attr_value(self, attr_name, use_default=True):
        """Return the value for an attribute.

        By default, this will return the default value for the attribute if
        it's not explicitly set.

        Args:
            attr_name (unicode):
                The name of the attribute.

            use_default (bool, optional):
                Whether to return the default value for the attribute if it's
                not explicitly set.

        Returns:
            object:
            The value for the attribute.
        """
        try:
            return self.field_attrs[attr_name]
        except KeyError:
            if use_default:
                return self.get_attr_default(attr_name)

            return None

    def get_attr_default(self, attr_name):
        """Return the default value for an attribute.

        Args:
            attr_name (unicode):
                The attribute name.

        Returns:
            object:
            The default value for the attribute, or ``None``.
        """
        for defaults in (self._ATTRIBUTE_DEFAULTS.get(self.field_type, {}),
                         self._ATTRIBUTE_DEFAULTS['*']):
            try:
                return defaults[attr_name]
            except KeyError:
                continue

        return None

    def is_attr_value_default(self, attr_name):
        """Return whether an attribute is set to its default value.

        Args:
            attr_name (unicode):
                The attribute name.

        Returns:
            bool:
            ``True`` if the attribute's value is set to its default value.
            ``False`` if it has a custom value.
        """
        try:
            attr_value = self.field_attrs[attr_name]
        except KeyError:
            return True

        return attr_value == self.get_attr_default(attr_name)

    def diff(self, old_field_sig):
        """Diff against an older field signature.

        This will return a list of field names that have changed between
        this field signature and an older one.

        Args:
            old_field_sig (FieldSignature):
                The old field signature to diff against.

        Returns:
            list:
            The list of field names.

        Raises:
            TypeError:
                The old signature provided was not a
                :py:class:`FieldSignature`.
        """
        if not isinstance(old_field_sig, FieldSignature):
            raise TypeError('Must provide a FieldSignature to diff against, '
                            'not a %s.' % type(old_field_sig))

        changed_attrs = [
            attr
            for attr in (set(old_field_sig.field_attrs) |
                         set(self.field_attrs))
            if self.get_attr_value(attr) != old_field_sig.get_attr_value(attr)
        ]

        # See if the field type has changed.
        old_field_type = old_field_sig.field_type
        new_field_type = self.field_type

        if old_field_type is not new_field_type:
            try:
                field_type_changed = (old_field_type().get_internal_type() !=
                                      new_field_type().get_internal_type())
            except TypeError:
                # We can't instantiate those, so assume the field
                # type has indeed changed.
                field_type_changed = True

            if field_type_changed:
                changed_attrs.append('field_type')

        # FieldSignature.related_model is not a field attribute,
        # but we do need to track its changes.
        if old_field_sig.related_model != self.related_model:
            changed_attrs.append('related_model')

        return sorted(changed_attrs)

    def clone(self):
        """Clone the signature.

        Returns:
            FieldSignature:
            The cloned signature.
        """
        return FieldSignature(field_name=self.field_name,
                              field_type=self.field_type,
                              field_attrs=deepcopy(self.field_attrs),
                              related_model=self.related_model)

    def serialize(self, sig_version=LATEST_SIGNATURE_VERSION):
        """Serialize field data to a signature dictionary.

        Args:
            sig_version (int, optional):
                The signature version to serialize as. This always defaults
                to the latest.

        Returns:
            dict:
            The serialized data.

        Raises:
            django_evolution.errors.InvalidSignatureVersion:
                The signature version provided isn't supported.
        """
        validate_sig_version(sig_version)

        field_sig_dict = OrderedDict()

        if sig_version == 2:
            field_module = self.field_type.__module__

            # If the field lives in django.db.models.fields, update it to
            # use django.db.models instead. This is for compatibility across
            # all Django versions.
            if field_module.startswith('django.db.models.fields'):
                field_module = 'django.db.models'

            field_sig_dict['type'] = '%s.%s' % (field_module,
                                                self.field_type.__name__)

            if self.field_attrs:
                field_sig_dict['attrs'] = deepcopy(self.field_attrs)
        elif sig_version == 1:
            field_sig_dict['field_type'] = self.field_type
            field_sig_dict.update(self.field_attrs)

        if self.related_model:
            field_sig_dict['related_model'] = self.related_model

        return field_sig_dict

    def __eq__(self, other):
        """Return whether two field signatures are equal.

        Args:
            other (FieldSignature):
                The other field signature.

        Returns:
            bool:
            ``True`` if the field signatures are equal. ``False`` if they
            are not.
        """
        return (other is not None and
                self.field_name == other.field_name and
                self.field_type is other.field_type and
                dict.__eq__(self.field_attrs, other.field_attrs) and
                self.related_model == other.related_model)

    def __repr__(self):
        """Return a string representation of the signature.

        Returns:
            unicode:
            A string representation of the signature.
        """
        return ('<FieldSignature(field_name=%r, field_type=%r,'
                ' field_attrs=%r, related_model=%r)>'
                % (self.field_name, self.field_type, self.field_attrs,
                   self.related_model))


def validate_sig_version(sig_version):
    """Validate that a signature version is supported.

    Args:
        sig_version (int):
            The version of the signature to validate.

    Raises:
        django_evolution.errors.InvalidSignatureVersion:
            The signature version provided isn't supported.
    """
    assert isinstance(sig_version, int)

    if not (0 < sig_version <= LATEST_SIGNATURE_VERSION):
        raise InvalidSignatureVersion(sig_version)

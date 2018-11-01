from __future__ import unicode_literals

from django.conf import global_settings
from django.db import models
from django.db.models.fields.related import ForeignKey
from django.utils import six

from django_evolution.compat.apps import get_apps
from django_evolution.compat.datastructures import OrderedDict
from django_evolution.compat.db import (db_router_allows_migrate,
                                        db_router_allows_syncdb)
from django_evolution.compat.models import (GenericRelation,
                                            get_models,
                                            get_remote_field,
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


DEFAULT_SIGNATURE_VERSION = 1


class BaseSignature(object):
    """Base class for a signature."""

    @classmethod
    def deserialize(self, sig_dict, sig_version):
        """Deserialize the signature.

        Args:
            sig_dict (dict):
                The dictionary containing signature data.

            sig_version (int):
                The stored signature version.

        Returns:
            BaseSignature:
            The resulting signature class.
        """
        raise NotImplementedError

    def serialize(self, sig_version=DEFAULT_SIGNATURE_VERSION):
        """Serialize data to a signature dictionary.

        Args:
            sig_version (int):
                The signature version to serialize as.

        Returns:
            dict:
            The serialized data.
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
    def deserialize(cls, project_sig_dict, **kwargs):
        """Deserialize a serialized project signature.

        Args:
            project_sig_dict (dict):
                The dictionary containing project signature data.

            **kwargs (dict):
                Extra keyword arguments.

        Returns:
            ProjectSignature:
            The resulting signature instance.
        """
        sig_version = project_sig_dict['__version__']
        project_sig = cls()

        for key, value in six.iteritems(project_sig_dict):
            if key != '__version__':
                project_sig.add_app_sig(AppSignature.deserialize(
                    app_id=key,
                    app_sig_dict=value,
                    sig_version=sig_version))

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

    def serialize(self, sig_version=DEFAULT_SIGNATURE_VERSION):
        """Serialize project data to a signature dictionary.

        Args:
            sig_version (int):
                The signature version to serialize as.

        Returns:
            dict:
            The serialized data.
        """
        project_sig_dict = {
            '__version__': sig_version,
        }
        project_sig_dict.update(
            (app_id, app_sig.serialize(sig_version))
            for app_id, app_sig in six.iteritems(self._app_sigs)
        )

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
        return self._app_sigs == other._app_sigs

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
        app_sig = cls(app_id=get_app_label(app))

        for model in get_models(app):
            # Only include those models that can be synced.
            #
            # On Django 1.7 and up, we need to check if the model allows for
            # migrations (using allow_migrate_model).
            #
            # On older versions of Django, we check if the model allows for
            # synchronization to the database (allow_syncdb).
            if (db_router_allows_migrate(database, get_app_label(app),
                                         model) or
                db_router_allows_syncdb(database, model)):
                app_sig.add_model(model)

        return app_sig

    @classmethod
    def deserialize(cls, app_id, app_sig_dict, sig_version):
        """Deserialize a serialized application signature.

        Args:
            app_id (unicode):
                The application ID.

            app_sig_dict (dict):
                The dictionary containing application signature data.

            sig_version (int):
                The version of the serialized signature data.

        Returns:
            AppSignature:
            The resulting signature instance.
        """
        app_sig = cls(app_id=app_id)

        for model_name, model_sig_dict in six.iteritems(app_sig_dict):
            app_sig.add_model_sig(
                ModelSignature.deserialize(model_name, model_sig_dict,
                                           sig_version=sig_version))

        return app_sig

    def __init__(self, app_id):
        """Initialize the signature.

        Args:
            app_id (unicode):
                The ID of the application. This will be the application label.
        """
        self.app_id = app_id
        self._model_sigs = OrderedDict()

    @property
    def model_sigs(self):
        """The model signatures stored on the application signature."""
        return six.itervalues(self._model_sigs)

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

    def serialize(self, sig_version=DEFAULT_SIGNATURE_VERSION):
        """Serialize application data to a signature dictionary.

        Args:
            sig_version (int):
                The signature version to serialize as.

        Returns:
            dict:
            The serialized data.
        """
        app_sig_dict = OrderedDict()

        for model_name, model_sig in six.iteritems(self._model_sigs):
            app_sig_dict[model_name] = model_sig.serialize(sig_version)

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
        return (self.app_id == other.app_id and
                self._model_sigs == other._model_sigs)

    def __repr__(self):
        """Return a string representation of the signature.

        Returns:
            unicode:
            A string representation of the signature.
        """
        return ('<AppSignature(app_id=%r, models=%r)>'
                % (self.app_id, list(six.iterkeys(self._model_sigs))))


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
                        index_together=meta.index_together,
                        model_name=meta.object_name,
                        pk_column=six.text_type(meta.pk.column),
                        table_name=meta.db_table,
                        unique_together=meta.unique_together)
        model_sig._unique_together_applied = True

        if getattr(meta, 'indexes', None):
            for index in meta.original_attrs['indexes']:
                model_sig.add_index(index)

        for field in meta.local_fields + meta.local_many_to_many:
            # Don't generate a signature for generic relations.
            if not isinstance(field, GenericRelation):
                model_sig.add_field(field)

        return model_sig

    @classmethod
    def deserialize(cls, model_name, model_sig_dict, sig_version):
        """Deserialize a serialized model signature.

        Args:
            model_name (unicode):
                The model name.

            model_sig_dict (dict):
                The dictionary containing model signature data.

            sig_version (int):
                The version of the serialized signature data.

        Returns:
            ModelSignature:
            The resulting signature instance.
        """
        meta_sig_dict = model_sig_dict['meta']
        fields_sig_dict = model_sig_dict['fields']

        model_sig = cls(
            db_tablespace=meta_sig_dict.get('db_tablespace'),
            index_together=[
                tuple(index_together)
                for index_together in meta_sig_dict.get('index_together', [])
            ],
            model_name=model_name,
            pk_column=meta_sig_dict.get('pk_column'),
            table_name=meta_sig_dict.get('db_table'),
            unique_together=[
                tuple(unique_together)
                for unique_together in meta_sig_dict.get('unique_together', [])
            ])

        for index_sig_dict in meta_sig_dict.get('indexes', []):
            model_sig.add_index_sig(
                IndexSignature.deserialize(index_sig_dict=index_sig_dict,
                                           sig_version=sig_version))

        for field_name, field_sig_dict in six.iteritems(fields_sig_dict):
            model_sig.add_field_sig(
                FieldSignature.deserialize(field_name=field_name,
                                           field_sig_dict=field_sig_dict,
                                           sig_version=sig_version))

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
        self.index_together = index_together
        self.pk_column = pk_column
        self.unique_together = unique_together

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

    def serialize(self, sig_version=DEFAULT_SIGNATURE_VERSION):
        """Serialize model data to a signature dictionary.

        Args:
            sig_version (int):
                The signature version to serialize as.

        Returns:
            dict:
            The serialized data.
        """
        return {
            'meta': {
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
        return (self.table_name == other.table_name and
                self.db_tablespace == other.db_tablespace and
                self.index_sigs == other.index_sigs and
                self.index_together == other.index_together and
                self.model_name == other.model_name and
                self.pk_column == other.pk_column and
                self.unique_together == other.unique_together and
                self._field_sigs == other._field_sigs)

    def __repr__(self):
        """Return a string representation of the signature.

        Returns:
            unicode:
            A string representation of the signature.
        """
        return '<ModelSignature(model_name=%r)>' % self.model_name


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
        return cls(name=index.name,
                   fields=index.fields)

    @classmethod
    def deserialize(cls, index_sig_dict, sig_version):
        """Deserialize a serialized index signature.

        Args:
            index_sig_dict (dict):
                The dictionary containing index signature data.

            sig_version (int):
                The version of the serialized signature data.

        Returns:
            IndexSignature:
            The resulting signature instance.
        """
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

    def serialize(self, sig_version=DEFAULT_SIGNATURE_VERSION):
        """Serialize index data to a signature dictionary.

        Args:
            sig_version (int):
                The signature version to serialize as.

        Returns:
            dict:
            The serialized data.
        """
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
        return (self.name == other.name and
                self.fields == other.fields)

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
        field_sig = cls(field_name=field.name,
                        field_type=field_type)

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
                field_sig.field_attrs[attr] = value

        remote_field = get_remote_field(field)

        if remote_field:
            remote_field_meta = get_remote_field_model(remote_field)._meta

            field_sig.field_attrs['related_model'] = '%s.%s' % (
                remote_field_meta.app_label,
                remote_field_meta.object_name,
            )

        return field_sig

    @classmethod
    def deserialize(cls, field_name, field_sig_dict, sig_version):
        """Deserialize a serialized field signature.

        Args:
            field_name (unicode):
                The name of the field.

            field_sig_dict (dict):
                The dictionary containing field signature data.

            sig_version (int):
                The version of the serialized signature data.

        Returns:
            FieldSignature:
            The resulting signature instance.
        """
        field_type = field_sig_dict['field_type']
        field_sig = cls(field_name=field_name,
                        field_type=field_type)

        for attr in cls._iter_attrs_for_field_type(field_type):
            if hasattr(field_sig, attr):
                # This is stored on the field signature class itself, so
                # it's not attribute data we want to load.
                continue

            alias = cls._ATTRIBUTE_ALIASES.get(attr)

            if alias and alias in field_sig_dict:
                value = field_sig_dict[alias]
            elif attr in field_sig_dict:
                value = field_sig_dict[attr]
            else:
                # The signature didn't contain a value for this attribute.
                continue

            field_sig.field_attrs[attr] = value

        # Now handle special data from the signature not covered above.
        try:
            field_sig.field_attrs['related_model'] = \
                field_sig_dict['related_model']
        except KeyError:
            # The signature doesn't have it. Skip this.
            pass

        return field_sig

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

    def __init__(self, field_name, field_type):
        """Initialize the signature.

        Args:
            field_name (unicode):
                The name of the field.

            field_type (cls):
                The class for the field. This would be a subclass of
                :py:class:`django.db.models.Field`.
        """
        self.field_name = field_name
        self.field_type = field_type
        self.field_attrs = OrderedDict()

    def serialize(self, sig_version=DEFAULT_SIGNATURE_VERSION):
        """Serialize field data to a signature dictionary.

        Args:
            sig_version (int):
                The signature version to serialize as.

        Returns:
            dict:
            The serialized data.
        """
        field_sig_dict = {
            'field_type': self.field_type,
        }
        field_sig_dict.update(self.field_attrs)

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
        return (self.field_name == other.field_name and
                self.field_type == other.field_type and
                self.field_attrs == other.field_attrs and
                self.related_model == other.related_model)

    def __repr__(self):
        """Return a string representation of the signature.

        Returns:
            unicode:
            A string representation of the signature.
        """
        return ('<FieldSignature(field_name=%r, field_type=%r,'
                ' field_attrs=%r)>'
                % (self.field_name, self.field_type, self.field_attrs))


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

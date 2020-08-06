"""Database models for tracking project schema history."""

from __future__ import unicode_literals

import json

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_init
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from django_evolution.compat import six
from django_evolution.compat.datastructures import OrderedDict
from django_evolution.compat.py23 import pickle_dumps, pickle_loads
from django_evolution.compat.six import python_2_unicode_compatible
from django_evolution.signature import ProjectSignature


class VersionManager(models.Manager):
    """Manage Version models.

    This introduces a convenience function for finding the current Version
    model for the database.
    """

    def current_version(self, using=None):
        """Return the Version model for the current schema.

        This will find the Version with both the latest timestamp and the
        latest ID. It's here as a replacement for the old call to
        :py:meth:`latest`, which only operated on the timestamp and would
        find the wrong entry if two had the same exact timestamp.

        Args:
            using (unicode):
                The database alias name to use for the query. Defaults
                to ``None``, the default database.

        Raises:
            Version.DoesNotExist: No such version exists.

        Returns:
            Version: The current Version object for the database.
        """
        versions = self.using(using).order_by('-when', '-id')

        try:
            return versions[0]
        except IndexError:
            raise self.model.DoesNotExist


class SignatureField(models.TextField):
    """A field for loading and storing project signatures.

    This will handle deserializing any project signatures stored in the
    database, converting them into a
    :py:class:`~django_evolution.signatures.ProjectSignature`, and then
    writing a serialized version back to the database.
    """

    description = _('Signature')

    def contribute_to_class(self, cls, name):
        """Perform operations when added to a class.

        This will listen for when an instance is constructed in order to
        perform some initial work.

        Args:
            cls (type):
                The model class.

            name (str):
                The name of the field.
        """
        super(SignatureField, self).contribute_to_class(cls, name)

        post_init.connect(self._post_init, sender=cls)

    def value_to_string(self, obj):
        """Return a serialized string value from the field.

        Args:
            obj (django.db.models.Model):
                The model instance.

        Returns:
            unicode:
            The serialized string contents.
        """
        return self._dumps(self.value_from_object(obj))

    def to_python(self, value):
        """Return a ProjectSignature value from the field contents.

        Args:
            value (object):
                The current value assigned to the field. This might be
                serialized string content or a
                :py:class:`~django_evolution.signatures.ProjectSignature`
                instance.

        Returns:
            django_evolution.signatures.ProjectSignature:
            The project signature stored in the field.

        Raises:
            django.core.exceptions.ValidationError:
                The field contents are of an unexpected type.
        """
        if not value:
            return ProjectSignature()
        elif isinstance(value, six.string_types):
            if value.startswith('json!'):
                loaded_value = json.loads(value[len('json!'):],
                                          object_pairs_hook=OrderedDict)
            else:
                loaded_value = pickle_loads(value)

            return ProjectSignature.deserialize(loaded_value)
        elif isinstance(value, ProjectSignature):
            return value
        else:
            raise ValidationError(
                'Unsupported serialized signature type %s' % type(value),
                code='invalid',
                params={
                    'value': value,
                })

    def get_prep_value(self, value):
        """Return a prepared Python value to work with.

        This simply wraps :py:meth:`to_python`.

        Args:
            value (object):
                The current value assigned to the field. This might be
                serialized string content or a
                :py:class:`~django_evolution.signatures.ProjectSignature`
                instance.

        Returns:
            django_evolution.signatures.ProjectSignature:
            The project signature stored in the field.

        Raises:
            django.core.exceptions.ValidationError:
                The field contents are of an unexpected type.
        """
        return self.to_python(value)

    def get_db_prep_value(self, value, connection, prepared=False):
        """Return a prepared value for use in database operations.

        Args:
            value (object):
                The current value assigned to the field. This might be
                serialized string content or a
                :py:class:`~django_evolution.signatures.ProjectSignature`
                instance.

            connection (django.db.backends.base.BaseDatabaseWrapper):
                The database connection to operate on.

            prepared (bool, optional):
                Whether the value is already prepared for Python.

        Returns:
            unicode:
            The value prepared for database operations.
        """
        if not prepared:
            value = self.get_prep_value(value)

        return self._dumps(value)

    def _post_init(self, instance, **kwargs):
        """Handle the construction of a model instance.

        This will ensure the value set on the field is a valid
        :py:class:`~django_evolution.signatures.ProjectSignature` object.

        Args:
            instance (django.db.models.Model):
                The model instance being constructed.

            **kwargs (dict, unused):
                Additional keyword arguments from the signal.
        """
        setattr(instance, self.attname,
                self.to_python(self.value_from_object(instance)))

    def _dumps(self, data):
        """Serialize the project signature to a string.

        Args:
            data (object):
                The signature data to dump. This might be serialized string
                content or a
                :py:class:`~django_evolution.signatures.ProjectSignature`
                instance.

        Returns:
            unicode:
            The project signature stored in the field.

        Raises:
            TypeError:
                The data provided was not of a supported type.
        """
        if isinstance(data, six.string_types):
            return data
        elif isinstance(data, ProjectSignature):
            serialized_data = data.serialize()
            sig_version = serialized_data['__version__']

            if sig_version >= 2:
                return 'json!%s' % json.dumps(serialized_data)
            else:
                return pickle_dumps(serialized_data)
        else:
            raise TypeError('Unsupported signature type %s' % type(data))


@python_2_unicode_compatible
class Version(models.Model):
    signature = SignatureField()
    when = models.DateTimeField(default=now)

    objects = VersionManager()

    def is_hinted(self):
        """Return whether this is a hinted version.

        Hinted versions store a signature without any accompanying evolutions.

        Returns:
            bool:
            ``True`` if this is a hinted evolution. ``False`` if it's based on
            explicit evolutions.
        """
        return not self.evolutions.exists()

    def __str__(self):
        if self.is_hinted():
            return 'Hinted version, updated on %s' % self.when

        return 'Stored version, updated on %s' % self.when

    class Meta:
        ordering = ('-when',)
        db_table = 'django_project_version'


@python_2_unicode_compatible
class Evolution(models.Model):
    version = models.ForeignKey(Version,
                                related_name='evolutions',
                                on_delete=models.CASCADE)
    app_label = models.CharField(max_length=200)
    label = models.CharField(max_length=100)

    def __str__(self):
        return 'Evolution %s, applied to %s' % (self.label, self.app_label)

    class Meta:
        db_table = 'django_evolution'
        ordering = ('id',)

"""Support for diffing project signatures."""

from __future__ import unicode_literals

from django.db import models
from django.utils import six

from django_evolution.compat.models import get_model
from django_evolution.errors import EvolutionException
from django_evolution.mutations import (DeleteField, AddField, DeleteModel,
                                        ChangeField, ChangeMeta)
from django_evolution.signature import (ATTRIBUTE_DEFAULTS,
                                        has_indexes_changed,
                                        has_index_together_changed,
                                        has_unique_together_changed)


class NullFieldInitialCallback(object):
    """A placeholder for an initial value for a field.

    This is used in place of an initial value in mutations for fields that
    don't allow NULL values and don't have an explicit initial value set.
    It will show up in hinted evolutions as ``<<USER VALUE REQUIRED>>` and
    will fail to evolve.
    """

    def __init__(self, app_label, model_name, field_name):
        """Initialize the object.

        Args:
            app_label (unicode):
                The label of the application owning the model.

            model_name (unicode):
                The name of the model owning the field.

            field_name (unicode):
                The name of the field to return an initial value for.
        """
        self.app_label = app_label
        self.model_name = model_name
        self.field_name = field_name

    def __repr__(self):
        """Return a string representation of the object.

        This is used when outputting the value in a hinted evolution.

        Returns:
            unicode:
            ``<<USER VALUE REQUIRED>>``
        """
        return '<<USER VALUE REQUIRED>>'

    def __call__(self):
        """Handle calls on this object.

        This will raise an exception stating that the evolution cannot be
        performed.

        Raises:
            django_evolution.errors.EvolutionException:
                An error stating that an explicit initial value must be
                provided in place of this object.
        """
        raise EvolutionException(
            "Cannot use hinted evolution: AddField or ChangeField mutation "
            "for '%s.%s' in '%s' requires user-specified initial value."
            % (self.model_name, self.field_name, self.app_label))


def get_initial_value(app_label, model_name, field_name):
    """Return an initial value for a field.

    If a default has been provided on the field definition or the field allows
    for an empty string, that value will be used. Otherwise, a placeholder
    callable will be used. This callable cannot actually be used in an
    evolution, but will indicate that user input is required.

    Args:
        app_label (unicode):
            The label of the application owning the model.

        model_name (unicode):
            The name of the model owning the field.

        field_name (unicode):
            The name of the field to return an initial value for.

    Returns:
        object:
        The initial value used for the field. If one cannot be computed and
        the developer must provide an explicit one,
        :py:class:`NullFieldInitialCallback` will be returned.
    """
    model = get_model(app_label, model_name)
    field = model._meta.get_field(field_name)

    if field and (field.has_default() or
                  (field.empty_strings_allowed and field.blank)):
        return field.get_default()

    return NullFieldInitialCallback(app_label, model_name, field_name)


class Diff(object):
    """Generates diffs between project signatures.

    The resulting diff is contained in two attributes::

        self.changed = {
            app_label: {
                'changed': {
                    model_name : {
                        'added': [ list of added field names ]
                        'deleted': [ list of deleted field names ]
                        'changed': {
                            field: [ list of modified property names ]
                        },
                        'meta_changed': {
                            'indexes': new value
                            'index_together': new value
                            'unique_together': new value
                        }
                    }
                'deleted': [ list of deleted model names ]
            }
        }
        self.deleted = {
            app_label: [ list of models in deleted app ]
        }
    """

    def __init__(self, original_sig, current_sig):
        """Initialize the object.

        Args:
            original_sig (dict):
                The original signature for the diff.

            current_sig (dict):
                The current signature for the diff.
        """
        self.original_sig = original_sig
        self.current_sig = current_sig

        self.changed = {}
        self.deleted = {}

        orig_version = self.original_sig.get('__version__')
        cur_version = current_sig.get('__version__')

        if orig_version != 1:
            raise EvolutionException(
                'Unknown version identifier in original signature: %s'
                % orig_version)

        if cur_version != 1:
            raise EvolutionException(
                'Unknown version identifier in target signature: %s'
                % cur_version)

        for app_name, old_app_sig in six.iteritems(original_sig):
            # Ignore the __version__ tag.
            if app_name == '__version__':
                continue

            try:
                new_app_sig = current_sig[app_name]
            except KeyError:
                # The application has been deleted.
                self.deleted[app_name] = list(six.iterkeys(old_app_sig))
                continue

            deleted_models = []
            changed_models = {}

            # Process the models in the application, looking for changes to
            # fields and meta attributes.
            for model_name, old_model_sig in six.iteritems(old_app_sig):
                try:
                    new_model_sig = new_app_sig[model_name]
                except KeyError:
                    # The model has been deleted.
                    deleted_models.append(model_name)
                    continue

                old_fields = old_model_sig['fields']
                new_fields = new_model_sig['fields']

                # Go through all the fields, looking for changed and deleted
                # fields.
                changed_fields = {}
                deleted_fields = []

                for field_name, old_field_data in six.iteritems(old_fields):
                    try:
                        new_field_data = new_fields[field_name]
                    except KeyError:
                        # The field has been deleted.
                        deleted_fields.append(field_name)
                        continue

                    # Go through all the attributes on the field, looking for
                    # changes.
                    changed_field_attrs = []

                    for attr in (set(six.iterkeys(old_field_data)) |
                                 set(six.iterkeys(new_field_data))):
                        attr_default = ATTRIBUTE_DEFAULTS.get(attr)

                        old_value = old_field_data.get(attr, attr_default)
                        new_value = new_field_data.get(attr, attr_default)

                        if old_value != new_value:
                            try:
                                if (attr == 'field_type' and
                                    (old_value().get_internal_type() ==
                                     new_value().get_internal_type())):
                                    continue
                            except TypeError:
                                pass

                            # The field has been changed.
                            changed_field_attrs.append(attr)

                    if changed_field_attrs:
                        # There were attribute changes. Store those with the
                        # field.
                        changed_fields[field_name] = changed_field_attrs

                # Go through the list of of added fields and add any that
                # don't exist in the original field list.
                added_fields = [
                    field_name
                    for field_name in six.iterkeys(new_model_sig['fields'])
                    if field_name not in old_fields
                ]

                # Build a list of changes to Model.Meta attributes.
                meta_changed = []

                if has_unique_together_changed(old_model_sig, new_model_sig):
                    meta_changed.append('unique_together')

                if has_index_together_changed(old_model_sig, new_model_sig):
                    meta_changed.append('index_together')

                if has_indexes_changed(old_model_sig, new_model_sig):
                    meta_changed.append('indexes')

                # Build the dictionary of changes for the model.
                model_changes = dict(
                    (key, value)
                    for key, value in (('added', added_fields),
                                       ('changed', changed_fields),
                                       ('deleted', deleted_fields),
                                       ('meta_changed', meta_changed))
                    if value
                )

                if model_changes:
                    # There are changes for this model. Store that in the
                    # diff.
                    changed_models[model_name] = model_changes

            # Build the dictionary of changes for the app.
            app_changes = dict(
                (key, value)
                for key, value in (('changed', changed_models),
                                   ('deleted', deleted_models))
                if value
            )

            if app_changes:
                # There are changes for this application. Store that in the
                # diff.
                self.changed[app_name] = app_changes

    def is_empty(self, ignore_apps=True):
        """Return whether the diff is empty.

        This is used to determine if both signatures are effectively equal. If
        ``ignore_apps`` is set, this will ignore changes caused by deleted
        applications.

        Args:
            ignore_apps (bool, optional):
                Whether to ignore changes to the applications list.

        Returns:
            bool:
            ``True`` if the diff is empty and signatures are equal.
            ``False`` if there are changes between the signatures.
        """
        if ignore_apps:
            return not self.changed
        else:
            return not self.deleted and not self.changed

    def __str__(self):
        """Return a string description of the diff.

        This will describe the changes found in the diff, for human
        consumption.

        Returns:
            unicode:
            The stirng representation of the diff.
        """
        lines = [
            'The application %s has been deleted' % app_label
            for app_label in self.deleted
        ]

        for app_label, app_changes in six.iteritems(self.changed):
            lines += [
                'The model %s.%s has been deleted' % (app_label, model_name)
                for model_name in app_changes.get('deleted', {})
            ]

            app_changed = app_changes.get('changed', {})

            for model_name, change in six.iteritems(app_changed):
                lines.append('In model %s.%s:' % (app_label, model_name))
                lines += [
                    "    Field '%s' has been added" % field_name
                    for field_name in change.get('added', [])
                ] + [
                    "    Field '%s' has been deleted" % field_name
                    for field_name in change.get('deleted', [])
                ]

                changed = change.get('changed', {})

                for field_name, field_change in six.iteritems(changed):
                    lines.append("    In field '%s':" % field_name)
                    lines += [
                        "        Property '%s' has changed" % prop
                        for prop in field_change
                    ]

                lines += [
                    "    Meta property '%s' has changed" % prop_name
                    for prop_name in change.get('meta_changed', [])
                ]

        return '\n'.join(lines)

    def evolution(self):
        """Return a list of mutations for resolving the diff.

        This will attempt to return a hinted evolution, consisting of a series
        of mutations for each affected application. These mutations will
        convert the database from the original to the target signatures.

        Returns:
            dict:
            A dictionary of mutations. Each key is an application label, and
            each value is a list of mutations for the application.
        """
        attr_default_keys = set(six.iterkeys(ATTRIBUTE_DEFAULTS))
        null_default = ATTRIBUTE_DEFAULTS['null']

        mutations = {}

        for app_label, app_changes in six.iteritems(self.changed):
            app_sig = self.current_sig[app_label]
            model_changes = app_changes.get('changed', {})
            app_mutations = []

            for model_name, model_change in six.iteritems(model_changes):
                model_sig = app_sig[model_name]

                # Process the list of added fields for the model.
                for field_name in model_change.get('added', {}):
                    field_sig = model_sig['fields'][field_name]
                    field_type = field_sig['field_type']

                    add_params = dict(
                        (key, value)
                        for key, value in six.iteritems(field_sig)
                        if key in attr_default_keys
                    )
                    add_params['field_type'] = field_type

                    if (field_type is not models.ManyToManyField and
                        not field_sig.get('null', null_default)):
                        # This field requires an initial value. Inject either
                        # a suitable initial value or a placeholder that must
                        # be filled in by the developer.
                        add_params['initial'] = \
                            get_initial_value(app_label, model_name,
                                              field_name)

                    if 'related_model' in field_sig:
                        add_params['related_model'] = \
                            six.text_type(field_sig['related_model'])

                    app_mutations.append(
                        AddField(model_name, field_name, **add_params))

                # Process the list of deleted fields for the model.
                app_mutations += [
                    DeleteField(model_name, field_name)
                    for field_name in model_change.get('deleted', [])
                ]

                # Process the list of changed fields for the model.
                field_changes = model_change.get('changed', {})

                for field_name, field_change in six.iteritems(field_changes):
                    field_sig = model_sig['fields'][field_name]
                    changed_attrs = {}

                    for attr in field_change:
                        if attr == 'related_model':
                            changed_attrs[attr] = field_sig[attr]
                        else:
                            changed_attrs[attr] = \
                                field_sig.get(attr, ATTRIBUTE_DEFAULTS[attr])

                    if ('null' in changed_attrs and
                        not field_sig.get('null', null_default) and
                        field_sig['field_type'] is not models.ManyToManyField):
                        # The field no longer allows null values, meaning an
                        # initial value is required. Inject either a suitable
                        # initial value or a placeholder that must be filled
                        # in by the developer.
                        changed_attrs['initial'] = \
                            get_initial_value(app_label, model_name,
                                              field_name)

                    app_mutations.append(ChangeField(model_name,
                                                     field_name,
                                                     **changed_attrs))

                # Process the Meta attribute changes for the model.
                app_mutations += [
                    ChangeMeta(model_name, prop_name,
                               model_sig['meta'].get(prop_name, []))
                    for prop_name in ('indexes',
                                      'index_together',
                                      'unique_together')
                    if prop_name in model_change.get('meta_changed', [])
                ]

            # Process the list of deleted models for the application.
            app_mutations += [
                DeleteModel(model_name)
                for model_name in app_changes.get('deleted', {})
            ]

            if app_mutations:
                mutations[app_label] = app_mutations

        return mutations

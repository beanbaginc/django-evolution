"""Support for diffing project signatures."""

from __future__ import unicode_literals

from django.db import models
from django.utils import six
from django.utils.translation import ugettext as _

from django_evolution.compat.datastructures import OrderedDict
from django_evolution.compat.models import get_model
from django_evolution.errors import EvolutionException
from django_evolution.mutations import (DeleteField, AddField, DeleteModel,
                                        ChangeField, ChangeMeta)
from django_evolution.signature import ProjectSignature


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
            _('Cannot use hinted evolution: AddField or ChangeField mutation '
              'for "%s.%s" in "%s" requires user-specified initial value.')
            % (self.model_name, self.field_name, self.app_label))


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

    def __init__(self, original_project_sig, target_project_sig):
        """Initialize the object.

        Args:
            original_project_sig (django_evolution.signature.ProjectSignature):
                The original project signature for the diff.

            target_project_sig (django_evolution.signature.ProjectSignature):
                The target project signature for the diff.
        """
        original_project_sig = \
            ProjectSignature.deserialize(original_project_sig)
        target_project_sig = \
            ProjectSignature.deserialize(target_project_sig)

        self.original_project_sig = original_project_sig
        self.target_project_sig = target_project_sig

        self.changed = OrderedDict()
        self.deleted = OrderedDict()

        for old_app_sig in original_project_sig.app_sigs:
            app_id = old_app_sig.app_id
            new_app_sig = target_project_sig.get_app_sig(app_id)

            if not new_app_sig:
                # The application has been deleted.
                self.deleted[app_id] = [
                    model_sig.model_name
                    for model_sig in old_app_sig.model_sigs
                ]
                continue

            deleted_models = []
            changed_models = OrderedDict()

            # Process the models in the application, looking for changes to
            # fields and meta attributes.
            for old_model_sig in old_app_sig.model_sigs:
                model_name = old_model_sig.model_name
                new_model_sig = new_app_sig.get_model_sig(model_name)

                if not new_model_sig:
                    # The model has been deleted.
                    deleted_models.append(model_name)
                    continue

                # Go through all the fields, looking for changed and deleted
                # fields.
                changed_fields = OrderedDict()
                deleted_fields = []

                for old_field_sig in old_model_sig.field_sigs:
                    field_name = old_field_sig.field_name
                    new_field_sig = new_model_sig.get_field_sig(field_name)

                    if not new_field_sig:
                        # The field has been deleted.
                        deleted_fields.append(field_name)
                        continue

                    # Go through all the attributes on the field, looking for
                    # changes.
                    changed_field_attrs = []

                    for attr in (set(old_field_sig.field_attrs) |
                                 set(new_field_sig.field_attrs)):
                        old_value = old_field_sig.get_attr_value(attr)
                        new_value = new_field_sig.get_attr_value(attr)

                        if old_value != new_value:
                            # The field has been changed.
                            changed_field_attrs.append(attr)

                    # See if the field type has changed.
                    old_field_type = old_field_sig.field_type
                    new_field_type = new_field_sig.field_type

                    if old_field_type is not new_field_type:
                        try:
                            field_type_changed = (
                                old_field_type().get_internal_type() !=
                                new_field_type().get_internal_type())
                        except TypeError:
                            # We can't instantiate those, so assume the field
                            # type has indeed changed.
                            field_type_changed = True

                        if field_type_changed:
                            changed_field_attrs.append('field_type')

                    # FieldSignature.related_model is not a field attribute,
                    # but we do need to track its changes.
                    if (old_field_sig.related_model !=
                        new_field_sig.related_model):
                        changed_field_attrs.append('related_model')

                    if changed_field_attrs:
                        # There were attribute changes. Store those with the
                        # field.
                        changed_fields[field_name] = \
                            sorted(changed_field_attrs)

                # Go through the list of added fields and add any that don't
                # exist in the original field list.
                added_fields = [
                    field_sig.field_name
                    for field_sig in new_model_sig.field_sigs
                    if not old_model_sig.get_field_sig(field_sig.field_name)
                ]

                # Build a list of changes to Model.Meta attributes.
                meta_changed = []

                if new_model_sig.has_unique_together_changed(old_model_sig):
                    meta_changed.append('unique_together')

                if (new_model_sig.index_together !=
                    old_model_sig.index_together):
                    meta_changed.append('index_together')

                if (list(new_model_sig.index_sigs) !=
                    list(old_model_sig.index_sigs)):
                    meta_changed.append('indexes')

                # Build the dictionary of changes for the model.
                model_changes = OrderedDict(
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
            app_changes = OrderedDict(
                (key, value)
                for key, value in (('changed', changed_models),
                                   ('deleted', deleted_models))
                if value
            )

            if app_changes:
                # There are changes for this application. Store that in the
                # diff.
                self.changed[app_id] = app_changes

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
        """Return the mutations needed for resolving the diff.

        This will attempt to return a hinted evolution, consisting of a series
        of mutations for each affected application. These mutations will
        convert the database from the original to the target signatures.

        Returns:
            collections.OrderedDict:
            An ordered dictionary of mutations. Each key is an application
            label, and each value is a list of mutations for the application.
        """
        mutations = OrderedDict()

        for app_label, app_changes in six.iteritems(self.changed):
            app_sig = self.target_project_sig.get_app_sig(app_label)
            model_changes = app_changes.get('changed', {})
            app_mutations = []

            for model_name, model_change in six.iteritems(model_changes):
                model_sig = app_sig.get_model_sig(model_name)

                # Process the list of added fields for the model.
                for field_name in model_change.get('added', {}):
                    field_sig = model_sig.get_field_sig(field_name)
                    field_type = field_sig.field_type

                    add_params = field_sig.field_attrs.copy()
                    add_params['field_type'] = field_type

                    if (not issubclass(field_type, models.ManyToManyField) and
                        not field_sig.get_attr_value('null')):
                        # This field requires an initial value. Inject either
                        # a suitable initial value or a placeholder that must
                        # be filled in by the developer.
                        add_params['initial'] = \
                            self._get_initial_value(app_label=app_label,
                                                    model_name=model_name,
                                                    field_name=field_name)

                    if field_sig.related_model:
                        add_params['related_model'] = field_sig.related_model

                    app_mutations.append(AddField(
                        model_name=model_name,
                        field_name=field_name,
                        **add_params))

                # Process the list of deleted fields for the model.
                app_mutations += [
                    DeleteField(model_name=model_name,
                                field_name=field_name)
                    for field_name in model_change.get('deleted', [])
                ]

                # Process the list of changed fields for the model.
                field_changes = model_change.get('changed', {})

                for field_name, field_change in six.iteritems(field_changes):
                    field_sig = model_sig.get_field_sig(field_name)
                    changed_attrs = OrderedDict(
                        (attr, field_sig.get_attr_value(attr))
                        for attr in field_change
                    )

                    if ('null' in changed_attrs and
                        not field_sig.get_attr_value('null') and
                        not issubclass(field_sig.field_type,
                                       models.ManyToManyField)):
                        # The field no longer allows null values, meaning an
                        # initial value is required. Inject either a suitable
                        # initial value or a placeholder that must be filled
                        # in by the developer.
                        changed_attrs['initial'] = \
                            self._get_initial_value(app_label=app_label,
                                                    model_name=model_name,
                                                    field_name=field_name)

                    if 'related_model' in field_change:
                        changed_attrs['related_model'] = \
                            field_sig.related_model

                    app_mutations.append(ChangeField(
                        model_name=model_name,
                        field_name=field_name,
                        **changed_attrs))

                # Process the Meta attribute changes for the model.
                meta_changed = model_change.get('meta_changed', [])

                # First, check if the Meta.indexes property has any changes.
                # They'll all be assembled into a single ChangeMeta.
                if 'indexes' in meta_changed:
                    change_meta_indexes = []

                    for index_sig in model_sig.index_sigs:
                        change_meta_index = {
                            'fields': index_sig.fields,
                        }

                        if index_sig.name:
                            change_meta_index['name'] = index_sig.name

                        change_meta_indexes.append(change_meta_index)

                    app_mutations.append(ChangeMeta(
                        model_name=model_name,
                        prop_name='indexes',
                        new_value=change_meta_indexes))

                # Then check Meta.index_together and Meta.unique_together.
                app_mutations += [
                    ChangeMeta(model_name=model_name,
                               prop_name=prop_name,
                               new_value=getattr(model_sig, prop_name) or [])
                    for prop_name in ('index_together', 'unique_together')
                    if prop_name in meta_changed
                ]

            # Process the list of deleted models for the application.
            app_mutations += [
                DeleteModel(model_name=model_name)
                for model_name in app_changes.get('deleted', {})
            ]

            if app_mutations:
                mutations[app_label] = app_mutations

        return mutations

    def _get_initial_value(self, app_label, model_name, field_name):
        """Return an initial value for a field.

        If a default has been provided on the field definition or the field
        allows for an empty string, that value will be used. Otherwise, a
        placeholder callable will be used. This callable cannot actually be
        used in an evolution, but will indicate that user input is required.

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

        return NullFieldInitialCallback(app_label=app_label,
                                        model_name=model_name,
                                        field_name=field_name)

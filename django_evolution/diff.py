"""Support for diffing project signatures."""

from __future__ import unicode_literals

from django.db import models
from django.utils.translation import ugettext as _

from django_evolution.compat import six
from django_evolution.compat.datastructures import OrderedDict
from django_evolution.compat.models import get_model
from django_evolution.errors import EvolutionException
from django_evolution.mutations import (AddField,
                                        ChangeField,
                                        ChangeMeta,
                                        DeleteField,
                                        DeleteModel,
                                        RenameAppLabel)
from django_evolution.signature import ProjectSignature


class NullFieldInitialCallback(object):
    """A placeholder for an initial value for a field.

    This is used in place of an initial value in mutations for fields that
    don't allow NULL values and don't have an explicit initial value set.
    It will show up in hinted evolutions as ``<<USER VALUE REQUIRED>>`` and
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
                            'constraints': new value
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
        assert isinstance(original_project_sig, ProjectSignature), \
               'original_project_sig must be a ProjectSignature instance'
        assert isinstance(target_project_sig, ProjectSignature), \
               'target_project_sig must be a ProjectSignature instance'

        self.original_project_sig = original_project_sig
        self.target_project_sig = target_project_sig

        diff = target_project_sig.diff(original_project_sig)

        self.changed = diff.get('changed', OrderedDict())
        self.deleted = diff.get('deleted', OrderedDict())

        self._mutations = None

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
            The string representation of the diff.
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

            app_meta_changed = app_changes.get('meta_changed', {})

            if app_meta_changed:
                lines.append('In app %s:' % app_label)

                if ('app_id' in app_meta_changed or
                    'legacy_app_label' in app_meta_changed):
                    lines.append('    App label has changed')

                if 'upgrade_method' in app_meta_changed:
                    lines.append('    Schema upgrade method changed')

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
        if self._mutations is not None:
            return self._mutations

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

                # Check if the Meta.constraints property has any changes.
                # They'll all be assembled into a single ChangeMeta.
                if 'constraints' in meta_changed:
                    app_mutations.append(ChangeMeta(
                        model_name=model_name,
                        prop_name='constraints',
                        new_value=[
                            dict({
                                'type': constraint_sig.type,
                                'name': constraint_sig.name,
                            }, **constraint_sig.attrs)
                            for constraint_sig in model_sig.constraint_sigs
                        ]))

                # Check if the Meta.indexes property has any changes.
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

                # Check Meta.index_together and Meta.unique_together.
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

            # See if any important details about the app have changed.
            meta_changed = app_changes.get('meta_changed', {})
            app_label_changed = meta_changed.get('app_id', {})
            legacy_app_label_changed = meta_changed.get('legacy_app_label', {})

            if app_label_changed or legacy_app_label_changed:
                app_mutations.append(RenameAppLabel(
                    app_label_changed.get('old', app_sig.app_id),
                    app_label_changed.get('new', app_sig.app_id),
                    legacy_app_label=legacy_app_label_changed.get(
                        'new', app_sig.legacy_app_label)))

            if app_mutations:
                mutations[app_label] = app_mutations

        self._mutations = mutations

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

"""Mutation that renames the app label for an application.

Version Added:
    2.2
"""

from __future__ import unicode_literals

from django_evolution.consts import UpgradeMethod
from django_evolution.mutations.base import BaseMutation
from django_evolution.signature import AppSignature


class RenameAppLabel(BaseMutation):
    """A mutation that renames the app label for an application.

    Version Changed:
        2.2:
        Moved into the :py:mod:`django_evolution.mutations.rename_app_label`
        module.
    """

    def __init__(self, old_app_label, new_app_label, legacy_app_label=None,
                 model_names=None):
        super(RenameAppLabel, self).__init__()

        self.old_app_label = old_app_label
        self.new_app_label = new_app_label
        self.legacy_app_label = legacy_app_label

        if model_names is None:
            self.model_names = None
        else:
            self.model_names = set(model_names)

    def get_hint_params(self):
        params = [
            self.serialize_value(self.old_app_label),
            self.serialize_value(self.new_app_label),
        ]

        if self.legacy_app_label:
            params.append(self.serialize_attr('legacy_app_label',
                                              self.legacy_app_label))

        return params

    def is_mutable(self, app_label, project_sig, database_state, database):
        """Return whether the mutation can be applied to the database.

        Args:
            app_label (unicode):
                The label for the Django application to be mutated.

            project_sig (dict, unused):
                The project's schema signature.

            database_state (django_evolution.db.state.DatabaseState, unused):
                The database state.

            database (unicode):
                The name of the database the operation would be performed on.

        Returns:
            bool:
            ``True`` if the mutation can run. ``False`` if it cannot.
        """
        return True

    def simulate(self, simulation):
        """Simulate the mutation.

        This will alter the signature to make any changes needed for the
        application's evolution storage.
        """
        old_app_label = self.old_app_label
        new_app_label = self.new_app_label
        model_names = self.model_names

        project_sig = simulation.project_sig
        old_app_sig = project_sig.get_app_sig(old_app_label, required=True)

        # Begin building the new AppSignature. For at least a short time, both
        # the old and new will exist, as we begin moving some or all of the old
        # to the new. The old will only be removed if it's empty after the
        # rename (so that we don't get rid of anything if there's two apps
        # sharing the same old app ID in the signature).
        new_app_sig = AppSignature(app_id=new_app_label,
                                   legacy_app_label=self.legacy_app_label,
                                   upgrade_method=UpgradeMethod.EVOLUTIONS)
        project_sig.add_app_sig(new_app_sig)

        if model_names is None:
            # Move over every single model listed under the app's signature.
            model_sigs = [
                model_sig
                for model_sig in old_app_sig.model_sigs
            ]
        else:
            # Move over only the requested models, in case the app signature
            # has the contents of two separate apps merged. Each will be
            # validated by way of simulation.get_model_sig.
            model_sigs = [
                simulation.get_model_sig(model_name)
                for model_name in model_names
            ]

        # Copy over the models.
        for model_sig in model_sigs:
            old_app_sig.remove_model_sig(model_sig.model_name)
            new_app_sig.add_model_sig(model_sig)

        if old_app_sig.is_empty():
            # The old app is now empty. We can remove the signature.
            project_sig.remove_app_sig(old_app_sig.app_id)

        # Update the simulation to refer to the new label.
        simulation.app_label = new_app_label

        # Go through the model signatures and update any that have a
        # related_model property referencing the old app label.
        for cur_app_sig in project_sig.app_sigs:
            for cur_model_sig in cur_app_sig.model_sigs:
                for cur_field_sig in cur_model_sig.field_sigs:
                    if cur_field_sig.related_model:
                        parts = cur_field_sig.related_model.split('.', 1)[1]

                        if parts[0] == old_app_label:
                            cur_field_sig.related_model = \
                                '%s.%s' % (new_app_label, parts[1])

    def mutate(self, mutator):
        """Schedule an app mutation on the mutator.

        This will inform the mutator of the new app label, for use in any
        future operations.

        Args:
            mutator (django_evolution.mutators.AppMutator):
                The mutator to perform an operation on.
        """
        mutator.app_label = self.new_app_label

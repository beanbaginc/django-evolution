"""Mutations for models, fields, and applications.

Version Changed:
    2.2:
    The classes have all been moved to nested modules. This module will
    provide forwarding imports, and will continue to be the primary place to
    import these mutations.

.. autosummary::
   :nosignatures:

   ~django_evolution.mutations.add_field.AddField
   ~django_evolution.mutations.base.BaseModelFieldMutation
   ~django_evolution.mutations.base.BaseModelMutation
   ~django_evolution.mutations.base.BaseUpgradeMethodMutation
   ~django_evolution.mutations.base.BaseMutation
   ~django_evolution.mutations.base.Simulation
   ~django_evolution.mutations.change_field.ChangeField
   ~django_evolution.mutations.change_meta.ChangeMeta
   ~django_evolution.mutations.delete_application.DeleteApplication
   ~django_evolution.mutations.delete_field.DeleteField
   ~django_evolution.mutations.delete_model.DeleteModel
   ~django_evolution.mutations.move_to_django_migrations.MoveToDjangoMigrations
   ~django_evolution.mutations.rename_app_label.RenameAppLabel
   ~django_evolution.mutations.rename_field.RenameField
   ~django_evolution.mutations.rename_model.RenameModel
   ~django_evolution.mutations.sql_mutation.SQLMutation
"""

from __future__ import unicode_literals

from django_evolution.mutations.add_field import AddField
from django_evolution.mutations.base import (BaseModelFieldMutation,
                                             BaseModelMutation,
                                             BaseUpgradeMethodMutation,
                                             BaseMutation,
                                             Simulation)
from django_evolution.mutations.change_field import ChangeField
from django_evolution.mutations.change_meta import ChangeMeta
from django_evolution.mutations.delete_application import DeleteApplication
from django_evolution.mutations.delete_field import DeleteField
from django_evolution.mutations.delete_model import DeleteModel
from django_evolution.mutations.move_to_django_migrations import \
    MoveToDjangoMigrations
from django_evolution.mutations.rename_app_label import RenameAppLabel
from django_evolution.mutations.rename_field import RenameField
from django_evolution.mutations.rename_model import RenameModel
from django_evolution.mutations.sql_mutation import SQLMutation


__all__ = (
    'AddField',
    'BaseModelFieldMutation',
    'BaseModelMutation',
    'BaseMutation',
    'BaseUpgradeMethodMutation',
    'ChangeField',
    'ChangeMeta',
    'DeleteApplication',
    'DeleteField',
    'DeleteModel',
    'MoveToDjangoMigrations',
    'RenameAppLabel',
    'RenameField',
    'RenameModel',
    'SQLMutation',
    'Simulation',
)

__autodoc_excludes__ = __all__

"""Patch to prevent db_index on ForeignKey fields from becoming reset on MySQL.

This applies to Django 1.8 through 1.10. These versions have code that is
supposed to *temporarily* unset ``db_index`` on a
:py:class:`~django.db.models.ForeignKey`, in order to prevent some SQL from
being generated, but it never restores this flag. This prevents us from storing
the right values.

This patch backs up the old values and restores them.
"""

from __future__ import unicode_literals

import django

try:
    # Django >= 1.7
    from django.db.backends.mysql.schema import DatabaseSchemaEditor
except ImportError:
    # Django < 1.7
    DatabaseSchemaEditor = None


def needs_patch():
    """Return whether the MySQL model indexes code needs to be patched.

    It will need patching if the running on Django 1.8 through 1.10. There
    isn't a more specific check we can put in place.

    Returns:
        bool:
        ``True`` if the backend needs to be patched. ``False`` if it does not.
    """
    return (1, 8) <= django.VERSION[:2] <= (1, 10)


def apply_patch():
    """Apply a patch to the base schema editor.

    This will override the ``_model_indexes_sql()`` method, making note of any
    :py:class:`~django.db.models.ForeignKey` fields that have ``db_index=True``
    set (the default), and restoring their values.
    """
    assert DatabaseSchemaEditor is not None

    def _model_indexes_sql(self, model):
        meta = model._meta
        db_indexed_fields = set(
            field.name
            for field in meta.local_fields
            if field.db_index and field.get_internal_type() == 'ForeignKey'
        )

        try:
            return orig_model_indexes_sql(self, model)
        finally:
            for field_name in db_indexed_fields:
                meta.get_field(field_name).db_index = True

    orig_model_indexes_sql = DatabaseSchemaEditor._model_indexes_sql
    DatabaseSchemaEditor._model_indexes_sql = _model_indexes_sql

"""Patch to add missing unique index name quoting on Django 2.0.x."""

from __future__ import unicode_literals

try:
    # Django >= 2.0
    from django.db.backends.base.schema import BaseDatabaseSchemaEditor
    from django.db.backends.ddl_references import IndexName
except ImportError:
    # Django < 1.7
    BaseDatabaseSchemaEditor = None
    IndexName = None


def needs_patch():
    """Return whether the unique index name generation needs patching.

    It will need patching if the SchemaEditor has a ``_create_unique_sql``
    method (added on Django 2.0.x, removed for 2.1.0).

    Returns:
        bool:
        ``True`` if the backend needs to be patched. ``False`` if it does not.
    """
    return (IndexName is not None and
            hasattr(BaseDatabaseSchemaEditor, '_create_unique_sql'))


def apply_patch():
    """Apply a patch to the base schema editor.

    This will override the ``_create_unique_sql()`` method, which generates
    the SQL for a ``CREATE UNIQUE INDEX`` statement, forcing the index name
    to be quoted. This is common across all Django database backends.
    """
    assert BaseDatabaseSchemaEditor is not None

    def _create_unique_sql(self, *args, **kwargs):
        from django.db.backends.ddl_references import IndexName

        statement = orig_create_unique_sql(self, *args, **kwargs)

        if statement is not None:
            index_name = statement.parts['name']

            if (isinstance(index_name, IndexName) and
                index_name.create_index_name == self._create_index_name):
                # The result will be unquoted. Let's quote it.
                index_name.create_index_name = lambda *args, **kwargs: \
                    self.quote_name(self._create_index_name(*args, **kwargs))

        return statement

    orig_create_unique_sql = BaseDatabaseSchemaEditor._create_unique_sql
    BaseDatabaseSchemaEditor._create_unique_sql = _create_unique_sql

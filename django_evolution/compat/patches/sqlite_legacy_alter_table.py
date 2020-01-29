"""Patch to enable SQLite Legacy Alter Table support."""

from __future__ import unicode_literals

import sqlite3

import django
from django.db.backends.sqlite3.base import DatabaseWrapper


def needs_patch():
    """Return whether the SQLite backend needs patching.

    It will need patching if using Django 1.11 through 2.1.4 while using
    SQLite3 v2.26.

    Returns:
        bool:
        ``True`` if the backend needs to be patched. ``False`` if it does not.
    """
    return (sqlite3.sqlite_version_info > (2, 26, 0) and
            (1, 11) <= django.VERSION < (2, 1, 5))


def apply_patch():
    """Apply a patch to the SQLite database backend.

    This will turn on SQLite's ``legacy_alter_table`` mode on when modifying
    the schema, which is needed in order to successfully allow Django to make
    table modifications.
    """
    class DatabaseSchemaEditor(DatabaseWrapper.SchemaEditorClass):
        def __enter__(self):
            with self.connection.cursor() as c:
                c.execute('PRAGMA legacy_alter_table = ON')

            return super(DatabaseSchemaEditor, self).__enter__()

        def __exit__(self, *args, **kwargs):
            super(DatabaseSchemaEditor, self).__exit__(*args, **kwargs)

            with self.connection.cursor() as c:
                c.execute('PRAGMA legacy_alter_table = OFF')

    DatabaseWrapper.SchemaEditorClass = DatabaseSchemaEditor

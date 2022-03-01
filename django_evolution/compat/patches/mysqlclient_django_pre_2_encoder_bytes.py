"""Patch to fix mysqlclient 2.1+ compatibility with Django 1.11 and older.

Django 1.11 and older would attempt to modify ``mysqlclient``'s internal type
conversion map after construction, mapping their safe versions of strings and
bytes to the converters.

This broke on Python 3, due to ``bytes`` no longer being implicitly in the
conversion map (as it was no longer the same as a string). While the
``mysqlclient`` developers worked around this in a point release, they removed
that support in 2.1.

This patch adds the missing entry to the initial map that Django provides.
Django still uses the wrong approach, but won't fail with a key lookup on
``bytes``.

Version Added:
    2.1.3
"""

from __future__ import unicode_literals


def needs_patch():
    """Return whether the MySQL backend needs patching.

    It will need patching if using mysqlclient >= 2.1 and Django <= 1.11.

    Returns:
        bool:
        ``True`` if the backend needs to be patched. ``False`` if it does not.
    """
    import django

    if django.VERSION[0] >= 2:
        # This was fixed in Django 2.0.
        return False

    # Make sure that both the MySQL backend and the MySQL version information
    # can be loaded.
    try:
        import django.db.backends.mysql.base
    except Exception:
        # There's no MySQL support to patch, or something unusual went wrong.
        return False

    return True


def apply_patch():
    """Apply a patch to the MySQL database backend.

    This will add the ``bytes`` conversion to Django's initial conversion map,
    so that it can find it when later altering the database connection's
    resulting map.
    """
    from django.db.backends.mysql.base import django_conversions

    django_conversions[bytes] = bytes

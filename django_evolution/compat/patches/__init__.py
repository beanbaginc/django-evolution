"""Compatibility patchess for Python and Django versions."""

from __future__ import unicode_literals

from django_evolution.compat.patches import (
    django1_8__1_10_mysql_preserve_db_index,
    django2_0_quote_unique_index_name,
    sqlite_legacy_alter_table)


#: List of patches that can be applied.
patches = [
    django1_8__1_10_mysql_preserve_db_index,
    django2_0_quote_unique_index_name,
    sqlite_legacy_alter_table,
]


def apply_patches():
    """Apply any necessary patches.

    This will check which patches are required, applying them to the
    runtime environment.
    """
    for patch in patches:
        if patch.needs_patch():
            patch.apply_patch()

"""Compatibility patchess for Python and Django versions."""

from __future__ import unicode_literals

from importlib import import_module


#: List of patches that can be applied.
patches = [
    'python3_10_collection_imports',
    'django1_8__1_10_mysql_preserve_db_index',
    'django2_0_quote_unique_index_name',
    'mysqlclient_django_pre_2_encoder_bytes',
    'sqlite_legacy_alter_table',
]


_patches_applied = False


def apply_patches():
    """Apply any necessary patches.

    This will check which patches are required, applying them to the
    runtime environment.
    """
    global _patches_applied

    if not _patches_applied:
        for patch_name in patches:
            patch = import_module('%s.%s' % (__name__, patch_name))

            if patch.needs_patch():
                patch.apply_patch()

        _patches_applied = True

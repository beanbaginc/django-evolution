"""Compatibility support for Python and Django versions."""

from __future__ import unicode_literals

from django_evolution.compat.patches import apply_patches


# Apply all necessary patches.
apply_patches()

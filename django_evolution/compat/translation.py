"""Compatibility functions for string translation.

Version Added:
    2.2
"""

from __future__ import unicode_literals

import django

if django.VERSION[:2] >= (2, 0):
    from django.utils.translation import gettext, gettext_lazy, ngettext
else:
    from django.utils.translation import (ugettext as gettext,
                                          ugettext_lazy as gettext_lazy,
                                          ungettext as ngettext)


__all__ = [
    'gettext',
    'gettext_lazy',
    'ngettext',
]

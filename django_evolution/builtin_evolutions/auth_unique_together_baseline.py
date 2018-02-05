from __future__ import unicode_literals

from django_evolution.mutations import ChangeMeta


MUTATIONS = [
    ChangeMeta('Permission', 'unique_together',
               [('content_type', 'codename')]),
]

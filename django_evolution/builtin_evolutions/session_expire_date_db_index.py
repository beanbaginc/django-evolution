from __future__ import unicode_literals

from django_evolution.mutations import ChangeField


MUTATIONS = [
    ChangeField('Session', 'expire_date', initial=None, db_index=True)
]

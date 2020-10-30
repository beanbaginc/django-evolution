from __future__ import unicode_literals


BEFORE_EVOLUTIONS = [
    'evolutions_app',
    ('evolutions_app', 'second_evolution'),
]

AFTER_MIGRATIONS = [
    ('migrations_app', '0001_initial'),
]

MUTATIONS = []

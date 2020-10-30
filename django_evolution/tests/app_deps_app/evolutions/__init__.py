from __future__ import unicode_literals


BEFORE_EVOLUTIONS = [
    'evolutions_app2',
    ('evolutions_app2', 'second_evolution'),
]

AFTER_EVOLUTIONS = [
    'evolutions_app',
    ('evolutions_app', 'first_evolution'),
]

BEFORE_MIGRATIONS = [
    ('migrations_app2', '0002_add_field'),
]

AFTER_MIGRATIONS = [
    ('migrations_app', '0001_initial'),
]

SEQUENCE = [
    'test_evolution',
]

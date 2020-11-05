from __future__ import unicode_literals

from django.db import models

from django_evolution.mutations import AddField


BEFORE_EVOLUTIONS = [
    'evolutions_app',
    ('evolutions_app', 'second_evolution'),
]

AFTER_MIGRATIONS = [
    ('migrations_app', '0001_initial'),
]

MUTATIONS = [
    AddField('EvolutionsApp2TestModel', 'fkey', models.ForeignKey,
             related_model='evolutions_app.EvolutionsAppTestModel',
             null=True)
]

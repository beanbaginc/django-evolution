from __future__ import unicode_literals

from django.db import models

from django_evolution.mutations import AddField


MUTATIONS = [
    AddField('EvolutionsAppTestModel', 'char_field2', models.CharField,
             max_length=20),
]

from __future__ import annotations

from django_evolution.mutations import ChangeField


MUTATIONS = [
    ChangeField('EvolutionsAppTestModel', 'char_field',
                max_length=10, null=True),
    ChangeField('EvolutionsAppTestModel', 'char_field2',
                max_length=20, null=True),
]

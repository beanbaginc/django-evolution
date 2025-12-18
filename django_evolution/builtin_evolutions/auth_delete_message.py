from __future__ import annotations

from django_evolution.mutations import DeleteModel


MUTATIONS = [
    DeleteModel('Message')
]

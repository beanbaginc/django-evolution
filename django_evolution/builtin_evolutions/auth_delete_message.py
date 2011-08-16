from django.db import models

from django_evolution.mutations import DeleteModel


MUTATIONS = [
    DeleteModel('Message')
]


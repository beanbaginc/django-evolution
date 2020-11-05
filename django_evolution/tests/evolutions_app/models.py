from __future__ import unicode_literals

from django.db import models


class EvolutionsAppTestModel(models.Model):
    char_field = models.CharField(max_length=10, null=True)
    char_field2 = models.CharField(max_length=20, null=True)

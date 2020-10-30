from __future__ import unicode_literals

from django.db import models


class EvolutionsApp2TestModel(models.Model):
    char_field = models.CharField(max_length=10)

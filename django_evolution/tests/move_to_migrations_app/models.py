from __future__ import unicode_literals

from django.db import models


class MoveToMigrationsAppTestModel(models.Model):
    char_field = models.CharField(max_length=10)
    added_field = models.BooleanField(default=False)
    added_field2 = models.IntegerField(default=42)

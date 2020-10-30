from __future__ import unicode_literals

from django.db import models


class MigrationsApp2TestModel(models.Model):
    char_field = models.CharField(max_length=100)
    added_field = models.BooleanField(default=False)

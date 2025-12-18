from __future__ import annotations

from django.db import models


class MigrationsAppTestModel(models.Model):
    char_field = models.CharField(max_length=10)
    added_field = models.IntegerField(default=42)

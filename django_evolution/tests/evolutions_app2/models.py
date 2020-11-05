from __future__ import unicode_literals

from django.db import models

from django_evolution.tests.evolutions_app.models import EvolutionsAppTestModel


class EvolutionsApp2TestModel(models.Model):
    char_field = models.CharField(max_length=10)
    fkey = models.ForeignKey(EvolutionsAppTestModel,
                             on_delete=models.CASCADE,
                             null=True)


class EvolutionsApp2TestModel2(models.Model):
    fkey = models.ForeignKey(EvolutionsApp2TestModel,
                             on_delete=models.CASCADE,
                             null=True)
    int_field = models.IntegerField(default=100)

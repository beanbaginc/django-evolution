from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.db import models

from django_evolution.compat.models import GenericForeignKey
from django_evolution.diff import Diff
from django_evolution.tests.base_test_case import EvolutionTestCase


class DiffAnchor1(models.Model):
    value = models.IntegerField()


class DiffAnchor2(models.Model):
    value = models.IntegerField()


class DiffAnchor3(models.Model):
    value = models.IntegerField()

    # Host a generic key here, too.
    content_type = models.ForeignKey(ContentType,
                                     on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey('content_type', 'object_id')


class DiffBaseModel(models.Model):
    name = models.CharField(max_length=20)
    age = models.IntegerField()
    ref = models.ForeignKey(DiffAnchor1,
                            on_delete=models.CASCADE)


class DiffTests(EvolutionTestCase):
    """Testing signature functionality."""

    default_base_model = DiffBaseModel
    default_extra_models = [
        ('DiffAnchor1', DiffAnchor1),
        ('DiffAnchor2', DiffAnchor2),
        ('DiffAnchor3', DiffAnchor3),
    ]

    def test_diff_identical_model(self):
        """Testing Diff with identical signatures"""
        class DestModel(models.Model):
            name = models.CharField(max_length=20)
            age = models.IntegerField()
            ref = models.ForeignKey(DiffAnchor1,
                                    on_delete=models.CASCADE)

        end_sig = self.make_end_signatures(DestModel, 'TestModel')[1]
        d = Diff(self.start_sig, end_sig)

        self.assertTrue(d.is_empty())
        self.assertEqual(d.evolution(), {})

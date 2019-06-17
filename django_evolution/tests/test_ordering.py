from __future__ import unicode_literals

from django.db import models

from django_evolution.tests.base_test_case import EvolutionTestCase
from django_evolution.tests.models import BaseTestModel


class OrderingTests(EvolutionTestCase):
    """Testing ordering of operations."""
    def test_deleting_model_and_foreign_key(self):
        """Testing ordering when deleting model and foreign key to model"""
        # Regression case 41: If deleting a model and a foreign key to that
        # model, the key deletion needs to happen before the model deletion.
        class Case41Anchor(BaseTestModel):
            value = models.IntegerField()

        class Case41Model(BaseTestModel):
            value = models.IntegerField()
            ref = models.ForeignKey(Case41Anchor,
                                    on_delete=models.CASCADE)

        class UpdatedCase41Model(BaseTestModel):
            value = models.IntegerField()

        self.set_base_model(Case41Model,
                            extra_models=[('Case41Anchor', Case41Anchor)])

        self.register_model(UpdatedCase41Model, name='TestModel')
        end_sig = self.create_test_proj_sig(UpdatedCase41Model,
                                            name='TestModel')

        # Simulate the removal of Case41Anchor
        end_sig.get_app_sig('tests').remove_model_sig('Case41Anchor')

        self.perform_diff_test(
            end_sig,
            ("The model tests.Case41Anchor has been deleted\n"
             "In model tests.TestModel:\n"
             "    Field 'ref' has been deleted"),
            [
                "DeleteField('TestModel', 'ref')",
                "DeleteModel('Case41Anchor')",
            ])

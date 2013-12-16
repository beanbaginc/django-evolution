from django.db import models

from django_evolution.diff import Diff
from django_evolution.mutations import DeleteApplication
from django_evolution.tests.base_test_case import EvolutionTestCase


class AppDeleteAnchor1(models.Model):
    value = models.IntegerField()


class AppDeleteAnchor2(models.Model):
    value = models.IntegerField()

    class Meta:
        db_table = 'app_delete_custom_add_anchor_table'


class AppDeleteBaseModel(models.Model):
    char_field = models.CharField(max_length=20)
    int_field = models.IntegerField()
    anchor_fk = models.ForeignKey(AppDeleteAnchor1)
    anchor_m2m = models.ManyToManyField(AppDeleteAnchor2)


class AppDeleteCustomTableModel(models.Model):
    value = models.IntegerField()
    alt_value = models.CharField(max_length=20)

    class Meta:
        db_table = 'app_delete_custom_table_name'


class DeleteAppTests(EvolutionTestCase):
    """Testing DeleteApplication."""
    sql_mapping_key = 'delete_application'
    default_base_model = AppDeleteBaseModel
    default_extra_models = [
        ('AppDeleteAnchor1', AppDeleteAnchor1),
        ('AppDeleteAnchor2', AppDeleteAnchor2),
        ('CustomTestModel', AppDeleteCustomTableModel),
    ]

    def test_delete_app(self):
        """Testing DeleteApplication"""
        self._perform_delete_app_test(None,
                                      'DeleteApplicationWithoutDatabase')

    def test_delete_app_with_custom_database(self):
        """Testing DeleteApplication with custom database"""
        self._perform_delete_app_test('default', 'DeleteApplication')

    def _perform_delete_app_test(self, database, sql_name):
        # Simulate deletion of the app.
        end_sig = self.copy_sig(self.start_sig)
        end_sig.pop('tests')

        d = Diff(self.start_sig, end_sig)
        self.assertEqual(sorted(d.deleted.keys()), ['tests'])
        self.assertEqual(d.deleted['tests'],
                         ['TestModel', 'AppDeleteAnchor1', 'AppDeleteAnchor2',
                          'CustomTestModel'])

        mutation = DeleteApplication()
        self.perform_simulations([mutation], end_sig, ignore_apps=True)

        test_database_sig = self.copy_sig(self.database_sig)
        test_sig = self.copy_sig(self.start_sig)

        sql = mutation.mutate('tests', test_sig, test_database_sig,
                              database)

        self.assertEqual('\n'.join(sql), self.get_sql_mapping(sql_name))
from django_evolution.tests.utils import test_sql_mapping

tests = r"""
>>> from datetime import datetime
>>> from pprint import PrettyPrinter

>>> from django.db import models
>>> from django.db.models.loading import cache

>>> from django_evolution.mutations import AddField, DeleteField, DeleteApplication
>>> from django_evolution.tests.utils import test_proj_sig, execute_test_sql
>>> from django_evolution.diff import Diff
>>> from django_evolution import signature
>>> from django_evolution import models as test_app

>>> import copy

>>> class AppDeleteAnchor1(models.Model):
...     value = models.IntegerField()

>>> class AppDeleteAnchor2(models.Model):
...     value = models.IntegerField()
...     class Meta:
...         db_table = 'app_delete_custom_add_anchor_table'

>>> class AppDeleteBaseModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     anchor_fk = models.ForeignKey(AppDeleteAnchor1)
...     anchor_m2m = models.ManyToManyField(AppDeleteAnchor2)

>>> class AppDeleteCustomTableModel(models.Model):
...     value = models.IntegerField()
...     alt_value = models.CharField(max_length=20)
...     class Meta:
...         db_table = 'app_delete_custom_table_name'

# Store the base signatures
>>> anchors = [('AppDeleteAnchor1', AppDeleteAnchor1), ('AppDeleteAnchor2',AppDeleteAnchor2)]
>>> base_sig = test_proj_sig(('TestModel', AppDeleteBaseModel), *anchors)
>>> custom_table_sig = test_proj_sig(('TestModel', AppDeleteCustomTableModel))

# Register the test models with the Django app cache
>>> cache.register_models('tests', AppDeleteCustomTableModel, AppDeleteBaseModel, AppDeleteAnchor1, AppDeleteAnchor2)

>>> new_sig = test_proj_sig(('TestModel', AppDeleteBaseModel), *anchors)
>>> deleted_app_sig = new_sig.pop('django_evolution')

# >>> pp.pprint(new_sig)

>>> d = Diff(base_sig, new_sig)
>>> print d.deleted
{'django_evolution': ['AppDeleteAnchor1', 'TestModel', 'AppDeleteAnchor2']}

>>> test_sig = copy.deepcopy(base_sig)

>>> test_sql = []
>>> delete_app = DeleteApplication()
>>> for app_label in d.deleted.keys():
...     test_sql.append(delete_app.mutate(app_label, test_sig))
...     delete_app.simulate(app_label, test_sig)

>>> Diff(test_sig, new_sig).is_empty(ignore_apps=True)
True

>>> for sql_list in test_sql:
...     for sql in sql_list:
...         print sql
%(DeleteApplication)s

""" % test_sql_mapping('delete_application')
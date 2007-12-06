from django_evolution.tests.utils import test_sql_mapping

tests = r"""
>>> from django.db import models
>>> from django.db.models.loading import cache

>>> from django_evolution.mutations import DeleteModel
>>> from django_evolution.tests.utils import test_proj_sig, execute_test_sql
>>> from django_evolution.diff import Diff

>>> import copy
 
# Now, a useful test model we can use for evaluating diffs
>>> class DeleteModelAnchor(models.Model):
...     value = models.IntegerField()
>>> class BasicModel(models.Model):
...     value = models.IntegerField()
>>> class BasicWithM2MModel(models.Model):
...     value = models.IntegerField()
...     m2m = models.ManyToManyField(DeleteModelAnchor)
>>> class CustomTableModel(models.Model):
...     value = models.IntegerField()
...     class Meta:
...         db_table = 'custom_table_name'
>>> class CustomTableWithM2MModel(models.Model):
...     value = models.IntegerField()
...     m2m = models.ManyToManyField(DeleteModelAnchor)
...     class Meta:
...         db_table = 'another_custom_table_name'

# Model attrs
>>> base_models = (
...     ('DeleteModelAnchor', DeleteModelAnchor),
...     ('BasicModel', BasicModel),
...     ('BasicWithM2MModel', BasicWithM2MModel),
...     ('CustomTableModel', CustomTableModel),
...     ('CustomTableWithM2MModel', CustomTableWithM2MModel),
... )

# Store the base signature
>>> base_sig = test_proj_sig(*base_models)

# Register the test models with the Django app cache
>>> cache.register_models('tests', DeleteModelAnchor, BasicModel,
...     BasicWithM2MModel, CustomTableModel, CustomTableWithM2MModel)


# Delete a Model
>>> new_models = [m for m in base_models if m[0] != 'BasicModel']
>>> new_sig = test_proj_sig(*new_models)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["DeleteModel('BasicModel')"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(BasicModel)s

# Delete a model with an m2m field
>>> new_models = [m for m in base_models if m[0] != 'BasicWithM2MModel']
>>> new_sig = test_proj_sig(*new_models)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["DeleteModel('BasicWithM2MModel')"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(BasicWithM2MModel)s

# Delete a model with a custom table name
>>> new_models = [m for m in base_models if m[0] != 'CustomTableModel']
>>> new_sig = test_proj_sig(*new_models)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["DeleteModel('CustomTableModel')"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(CustomTableModel)s

# Delete a model with a custom table name and an m2m field
>>> new_models = [m for m in base_models if m[0] != 'CustomTableWithM2MModel']
>>> new_sig = test_proj_sig(*new_models)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["DeleteModel('CustomTableWithM2MModel')"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(CustomTableWithM2MModel)s
""" % test_sql_mapping('delete_model')

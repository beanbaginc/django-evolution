
tests = r"""
>>> from django.db import models
>>> from django_evolution.management import signature
>>> from django_evolution.management import diff
>>> from django_evolution import models as test_app
>>> from pprint import pprint
>>> class BaseModel(models.Model):
...     name = models.CharField(max_length=20)
...     age = models.IntegerField()

# You can create a model signature for a model
>>> base_sig = {'testapp': signature.create_model_sig(BaseModel) }
>>> pprint(base_sig['testapp'])
{'fields': {'age': {'column': 'age',
                    'db_column': None,
                    'db_index': False,
                    'db_tablespace': None,
                    'internal_type': 'IntegerField',
                    'max_length': None,
                    'null': False,
                    'primary_key': False,
                    'unique': False},
            'id': {'column': 'id',
                   'db_column': None,
                   'db_index': False,
                   'db_tablespace': None,
                   'internal_type': 'AutoField',
                   'max_length': None,
                   'null': False,
                   'primary_key': True,
                   'unique': False},
            'name': {'column': 'name',
                     'db_column': None,
                     'db_index': False,
                     'db_tablespace': None,
                     'internal_type': 'CharField',
                     'max_length': 20,
                     'null': False,
                     'primary_key': False,
                     'unique': False}},
 'meta': {'unique_together': []}}

# An identical model gives an empty Diff
>>> class TestModel(models.Model):
...     name = models.CharField(max_length=20)
...     age = models.IntegerField()

>>> test_sig = {'testapp': signature.create_model_sig(TestModel) }
>>> d = diff.Diff(test_app, base_sig, test_sig)
>>> d.is_empty()
True
>>> d.evolution()
[]

# Adding a field gives a non-empty diff
>>> class AddFieldModel(models.Model):
...     name = models.CharField(max_length=20)
...     age = models.IntegerField()
...     date_of_birth = models.DateField()

>>> test_sig = {'testapp': signature.create_model_sig(AddFieldModel) }
>>> d = diff.Diff(test_app, base_sig, test_sig)
>>> d.is_empty()
False
>>> len(d.evolution())
1
>>> print d
In model django_evolution.testapp:
    Field 'date_of_birth' has been added

# Deleting a field gives a non-empty diff
>>> class DeleteFieldModel(models.Model):
...     name = models.CharField(max_length=20)

>>> test_sig = {'testapp': signature.create_model_sig(DeleteFieldModel) }
>>> d = diff.Diff(test_app, base_sig, test_sig)
>>> d.is_empty()
False
>>> len(d.evolution())
1
>>> print d
In model django_evolution.testapp:
    Field 'age' has been deleted

# Renaming a field is caught as 2 diffs
# (For the moment - long term, this should hint as a Rename) 
>>> class RenameFieldModel(models.Model):
...     full_name = models.CharField(max_length=20)
...     age = models.IntegerField()

>>> test_sig = {'testapp': signature.create_model_sig(RenameFieldModel) }
>>> d = diff.Diff(test_app, base_sig, test_sig)
>>> d.is_empty()
False
>>> len(d.evolution())
2
>>> print d
In model django_evolution.testapp:
    Field 'full_name' has been added
    Field 'name' has been deleted
    
"""
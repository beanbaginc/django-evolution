
tests = r"""
>>> from django.db import models
>>> from django_evolution import signature
>>> from django_evolution.diff import Diff
>>> from django_evolution.tests.utils import test_proj_sig
>>> from pprint import pprint

# First, a model that has one of everything so we can validate all cases for a signature
>>> class Anchor1(models.Model):
...     value = models.IntegerField()
>>> class Anchor2(models.Model):
...     value = models.IntegerField()
>>> class Anchor3(models.Model):
...     value = models.IntegerField()

>>> class SigModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     null_field = models.IntegerField(null=True, db_column='size_column')
...     id_card = models.IntegerField(unique=True, db_index=True)
...     dec_field = models.DecimalField(max_digits=10, decimal_places=4)
...     ref1 = models.ForeignKey(Anchor1)
...     ref2 = models.ForeignKey(Anchor1, related_name='other_sigmodel')
...     ref3 = models.ForeignKey(Anchor2, db_column='value', db_index=True)
...     ref4 = models.ForeignKey('self')
...     ref5 = models.ManyToManyField(Anchor3)
...     ref6 = models.ManyToManyField(Anchor3, related_name='other_sigmodel')
...     ref7 = models.ManyToManyField('self')

# You can create a model signature for a model
>>> pprint(signature.create_model_sig(SigModel))
{'fields': {'char_field': {'field_type': <class 'django.db.models.fields.CharField'>,
                           'max_length': 20},
            'dec_field': {'decimal_places': 4,
                          'field_type': <class 'django.db.models.fields.DecimalField'>,
                          'max_digits': 10},
            'id': {'field_type': <class 'django.db.models.fields.AutoField'>,
                   'primary_key': True},
            'id_card': {'db_index': True,
                        'field_type': <class 'django.db.models.fields.IntegerField'>,
                        'unique': True},
            'int_field': {'field_type': <class 'django.db.models.fields.IntegerField'>},
            'null_field': {'db_column': 'size_column',
                           'field_type': <class 'django.db.models.fields.IntegerField'>,
                           'null': True},
            'ref1': {'field_type': <class 'django.db.models.fields.related.ForeignKey'>,
                     'related_model': 'django_evolution.Anchor1'},
            'ref2': {'field_type': <class 'django.db.models.fields.related.ForeignKey'>,
                     'related_model': 'django_evolution.Anchor1'},
            'ref3': {'db_column': 'value',
                     'field_type': <class 'django.db.models.fields.related.ForeignKey'>,
                     'related_model': 'django_evolution.Anchor2'},
            'ref4': {'field_type': <class 'django.db.models.fields.related.ForeignKey'>,
                     'related_model': 'django_evolution.SigModel'},
            'ref5': {'field_type': <class 'django.db.models.fields.related.ManyToManyField'>,
                     'related_model': 'django_evolution.Anchor3'},
            'ref6': {'field_type': <class 'django.db.models.fields.related.ManyToManyField'>,
                     'related_model': 'django_evolution.Anchor3'},
            'ref7': {'field_type': <class 'django.db.models.fields.related.ManyToManyField'>,
                     'related_model': 'django_evolution.SigModel'}},
 'meta': {'db_table': 'django_evolution_sigmodel',
          'db_tablespace': None,
          'pk_column': 'id',
          'unique_together': []}}

# Now, a useful test model we can use for evaluating diffs
>>> class BaseModel(models.Model):
...     name = models.CharField(max_length=20)
...     age = models.IntegerField()

>>> base_sig = test_proj_sig(BaseModel)

# An identical model gives an empty Diff
>>> class TestModel(models.Model):
...     name = models.CharField(max_length=20)
...     age = models.IntegerField()

>>> test_sig = test_proj_sig(TestModel)
>>> d = Diff(base_sig, test_sig)
>>> d.is_empty()
True
>>> d.evolution()
{}

# Adding a field gives a non-empty diff
>>> class AddFieldModel(models.Model):
...     name = models.CharField(max_length=20)
...     age = models.IntegerField()
...     date_of_birth = models.DateField()

>>> test_sig = test_proj_sig(AddFieldModel)
>>> d = Diff(base_sig, test_sig)
>>> d.is_empty()
False
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'date_of_birth', models.DateField)"]

# Deleting a field gives a non-empty diff
>>> class DeleteFieldModel(models.Model):
...     name = models.CharField(max_length=20)

>>> test_sig = test_proj_sig(DeleteFieldModel)
>>> d = Diff(base_sig, test_sig)
>>> d.is_empty()
False
>>> print [str(e) for e in d.evolution()['testapp']]
["DeleteField('TestModel', 'age')"]

# Renaming a field is caught as 2 diffs
# (For the moment - long term, this should hint as a Rename) 
>>> class RenameFieldModel(models.Model):
...     full_name = models.CharField(max_length=20)
...     age = models.IntegerField()

>>> test_sig = test_proj_sig(RenameFieldModel)
>>> d = Diff(base_sig, test_sig)
>>> d.is_empty()
False
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'full_name', models.CharField, max_length=20)", "DeleteField('TestModel', 'name')"]
    
"""
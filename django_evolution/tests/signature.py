
tests = r"""
>>> from django.db import models
>>> from django_evolution.management import signature
>>> from django_evolution.management import diff
>>> from django_evolution import models as test_app
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
{'fields': {'char_field': {'max_length': 20, 'internal_type': 'CharField'},
            'dec_field': {'decimal_places': 4,
                          'internal_type': 'DecimalField',
                          'max_digits': 10},
            'id': {'internal_type': 'AutoField', 'primary_key': True},
            'id_card': {'db_index': True,
                        'internal_type': 'IntegerField',
                        'unique': True},
            'int_field': {'internal_type': 'IntegerField'},
            'null_field': {'db_column': 'size_column',
                           'internal_type': 'IntegerField',
                           'null': True},
            'ref1': {'internal_type': 'ForeignKey',
                     'related_model': 'Anchor1'},
            'ref2': {'internal_type': 'ForeignKey',
                     'related_model': 'Anchor1'},
            'ref3': {'db_column': 'value',
                     'internal_type': 'ForeignKey',
                     'related_model': 'Anchor2'},
            'ref4': {'internal_type': 'ForeignKey',
                     'related_model': 'SigModel'},
            'ref5': {'internal_type': 'ManyToManyField',
                     'related_model': 'Anchor3'},
            'ref6': {'internal_type': 'ManyToManyField',
                     'related_model': 'Anchor3'},
            'ref7': {'internal_type': 'ManyToManyField',
                     'related_model': 'SigModel'}},
 'meta': {'db_table': 'django_evolution_sigmodel',
          'db_tablespace': None,
          'pk_column': 'id',
          'unique_together': []}}

# Now, a useful test model we can use for evaluating diffs
>>> class BaseModel(models.Model):
...     name = models.CharField(max_length=20)
...     age = models.IntegerField()

>>> base_sig = {
...     'TestModel': signature.create_model_sig(BaseModel), 
...     '__label__': 'testapp',
...     '__version__': 1,
... }

# An identical model gives an empty Diff
>>> class TestModel(models.Model):
...     name = models.CharField(max_length=20)
...     age = models.IntegerField()

>>> test_sig = {
...     'TestModel': signature.create_model_sig(TestModel), 
...     '__label__': 'testapp',
...     '__version__': 1,
... }

>>> d = diff.Diff(base_sig, test_sig)
>>> d.is_empty()
True
>>> d.evolution()
[]

# Adding a field gives a non-empty diff
>>> class AddFieldModel(models.Model):
...     name = models.CharField(max_length=20)
...     age = models.IntegerField()
...     date_of_birth = models.DateField()

>>> test_sig = {
...     'TestModel': signature.create_model_sig(AddFieldModel), 
...     '__label__': 'testapp',
...     '__version__': 1,
... }

>>> d = diff.Diff(base_sig, test_sig)
>>> d.is_empty()
False
>>> len(d.evolution())
1
>>> print [str(e) for e in d.evolution()]
["AddField('TestModel', 'date_of_birth', 'models.DateField')"]

# Deleting a field gives a non-empty diff
>>> class DeleteFieldModel(models.Model):
...     name = models.CharField(max_length=20)

>>> test_sig = {
...     'TestModel': signature.create_model_sig(DeleteFieldModel), 
...     '__label__': 'testapp',
...     '__version__': 1,
... }

>>> d = diff.Diff(base_sig, test_sig)
>>> d.is_empty()
False
>>> len(d.evolution())
1
>>> print [str(e) for e in d.evolution()]
["DeleteField('TestModel', 'age')"]

# Renaming a field is caught as 2 diffs
# (For the moment - long term, this should hint as a Rename) 
>>> class RenameFieldModel(models.Model):
...     full_name = models.CharField(max_length=20)
...     age = models.IntegerField()

>>> test_sig = {
...     'TestModel': signature.create_model_sig(RenameFieldModel), 
...     '__label__': 'testapp',
...     '__version__': 1,
... }
>>> d = diff.Diff(base_sig, test_sig)
>>> d.is_empty()
False
>>> len(d.evolution())
2
>>> print [str(e) for e in d.evolution()]
["AddField('TestModel', 'full_name', 'models.CharField', max_length=20)", "DeleteField('TestModel', 'name')"]
    
"""
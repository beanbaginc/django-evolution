from django_evolution.tests.utils import test_sql_mapping

tests = r"""
# The AddField tests will aim to test the following usecases:
# Field resulting in a new database column.
# Field resulting in a new database column with a non-default name.
# Field resulting in a new database column in a table with a non-default name.
# Primary key field.
# Indexed field
# Unique field.
# Null field
# 
# Foreign Key field.
# M2M field between models with default table names.
# M2M field between models with non-default table names.
# M2M field between self
>>> from datetime import datetime

>>> from django.db import models
>>> from django.db.models.loading import cache

>>> from django_evolution.mutations import AddField, DeleteField
>>> from django_evolution.tests.utils import test_proj_sig, execute_test_sql
>>> from django_evolution.diff import Diff
>>> from django_evolution import signature
>>> from django_evolution import models as test_app

>>> import copy

>>> class AddSequenceFieldInitial(object):
...     def __init__(self, suffix):
...         self.suffix = suffix
...
...     def __call__(self):
...         from django.db import connection
...         qn = connection.ops.quote_name
...         return qn('int_field')

>>> class AddAnchor1(models.Model):
...     value = models.IntegerField()

>>> class AddAnchor2(models.Model):
...     value = models.IntegerField()
...     class Meta:
...         db_table = 'custom_add_anchor_table'

>>> class AddBaseModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()

>>> class CustomTableModel(models.Model):
...     value = models.IntegerField()
...     alt_value = models.CharField(max_length=20)
...     class Meta:
...         db_table = 'custom_table_name'

# Store the base signatures
>>> anchors = [('AddAnchor1',AddAnchor1),('AddAnchor2',AddAnchor2)]
>>> base_sig = test_proj_sig(('TestModel',AddBaseModel), *anchors)
>>> custom_table_sig = test_proj_sig(('TestModel',CustomTableModel))

# Register the test models with the Django app cache
>>> cache.register_models('tests', CustomTableModel, AddBaseModel, AddAnchor1, AddAnchor2)

# Add non-null field with non-callable initial value
>>> class AddNonNullNonCallableDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.IntegerField()

>>> new_sig = test_proj_sig(('TestModel',AddNonNullNonCallableDatabaseColumnModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'added_field', models.IntegerField, initial=<<USER VALUE REQUIRED>>)"]

# First try without an initial value. This will fail
>>> evolution = [AddField('TestModel', 'added_field', models.IntegerField)]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)
Traceback (most recent call last):
...
SimulationFailure: Cannot create new column 'added_field' on 'django_evolution.TestModel' without a non-null initial value.

# Now try with an explicitly null initial value. This will also fail
>>> evolution = [AddField('TestModel', 'added_field', models.IntegerField, initial=None)]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)
Traceback (most recent call last):
...
SimulationFailure: Cannot create new column 'added_field' on 'django_evolution.TestModel' without a non-null initial value.

# Now try with a good initial value
>>> evolution = [AddField('TestModel', 'added_field', models.IntegerField, initial=1)]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql) #AddNonNullNonCallableDatabaseColumnModel
%(AddNonNullNonCallableDatabaseColumnModel)s

# Add non-null with callable initial value
>>> class AddNonNullCallableDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.IntegerField()

>>> new_sig = test_proj_sig(('TestModel',AddNonNullCallableDatabaseColumnModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'added_field', models.IntegerField, initial=<<USER VALUE REQUIRED>>)"]

# Now try with a good initial value
>>> evolution = [AddField('TestModel', 'added_field', models.IntegerField, initial=AddSequenceFieldInitial('AddNonNullCallableDatabaseColumnModel'))]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql) #AddNonNullCallableDatabaseColumnModel
%(AddNonNullCallableDatabaseColumnModel)s

# Add non-null with missing initial data
>>> class AddNonNullMissingInitialDataDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.IntegerField()

>>> new_sig = test_proj_sig(('TestModel',AddNonNullMissingInitialDataDatabaseColumnModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'added_field', models.IntegerField, initial=<<USER VALUE REQUIRED>>)"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)
Traceback (most recent call last):
...
EvolutionException: Cannot use hinted evolution: AddField or ChangeField mutation for 'TestModel.added_field' in 'django_evolution' requires user-specified initial value.

# Add nullable column with initial data
>>> class AddNullColumnWithInitialDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.IntegerField(null=True)

>>> new_sig = test_proj_sig(('TestModel',AddNullColumnWithInitialDatabaseColumnModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'added_field', models.IntegerField, null=True)"]

>>> evolution = [AddField('TestModel', 'added_field', models.IntegerField, initial=1, null=True)]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql) #AddNullColumnWithInitialDatabaseColumnModel
%(AddNullColumnWithInitialDatabaseColumnModel)s

# Add a field that requires string-form initial data
>>> class AddStringDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.CharField(max_length=10)

>>> new_sig = test_proj_sig(('TestModel',AddStringDatabaseColumnModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'added_field', models.CharField, initial=<<USER VALUE REQUIRED>>, max_length=10)"]

>>> evolution = [AddField('TestModel', 'added_field', models.CharField, initial="abc's xyz", max_length=10)]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql) #AddStringDatabaseColumnModel
%(AddStringDatabaseColumnModel)s

# Add a field that requires date-form initial data
>>> class AddDateDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.DateTimeField()

>>> new_sig = test_proj_sig(('TestModel',AddDateDatabaseColumnModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'added_field', models.DateTimeField, initial=<<USER VALUE REQUIRED>>)"]

>>> new_date = datetime(2007,12,13,16,42,0)
>>> evolution = [AddField('TestModel', 'added_field', models.DateTimeField, initial=new_date)]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql) #AddDateDatabaseColumnModel
%(AddDateDatabaseColumnModel)s

# Add column with default value
>>> class AddColumnWithDefaultDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.IntegerField(default=42)

>>> new_sig = test_proj_sig(('TestModel',AddColumnWithDefaultDatabaseColumnModel), *anchors)
>>> cache.app_models['django_evolution']['testmodel'] = AddColumnWithDefaultDatabaseColumnModel
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'added_field', models.IntegerField, initial=42)"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql) #AddNullColumnWithInitialDatabaseColumnModel
%(AddColumnWithDefaultDatabaseColumnModel)s

# Null field
>>> class NullDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.IntegerField(null=True)

>>> new_sig = test_proj_sig(('TestModel', NullDatabaseColumnModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'added_field', models.IntegerField, null=True)"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql) #NullDatabaseColumnModel
%(NullDatabaseColumnModel)s

# Field resulting in a new database column with a non-default name.
>>> class NonDefaultDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     add_field = models.IntegerField(db_column='non-default_column', null=True)

>>> new_sig = test_proj_sig(('TestModel',NonDefaultDatabaseColumnModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'add_field', models.IntegerField, null=True, db_column='non-default_column')"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql) #NonDefaultDatabaseColumnModel
%(NonDefaultDatabaseColumnModel)s

# Field resulting in a new database column in a table with a non-default name.
>>> class AddDatabaseColumnCustomTableModel(models.Model):
...     value = models.IntegerField()
...     alt_value = models.CharField(max_length=20)
...     added_field = models.IntegerField(null=True)
...     class Meta:
...         db_table = 'custom_table_name'


>>> new_sig = test_proj_sig(('TestModel',AddDatabaseColumnCustomTableModel), *anchors)
>>> d = Diff(custom_table_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'added_field', models.IntegerField, null=True)"]

>>> test_sig = copy.deepcopy(custom_table_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql) #AddDatabaseColumnCustomTableModel
%(AddDatabaseColumnCustomTableModel)s

# Add Primary key field.
# Delete of old Primary Key is prohibited.
>>> class AddPrimaryKeyModel(models.Model):
...     my_primary_key = models.AutoField(primary_key=True)
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()

>>> new_sig = test_proj_sig(('TestModel',AddPrimaryKeyModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'my_primary_key', models.AutoField, initial=<<USER VALUE REQUIRED>>, primary_key=True)", "DeleteField('TestModel', 'id')"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []

>>> for mutation in [AddField('TestModel', 'my_primary_key', models.AutoField, initial=AddSequenceFieldInitial('AddPrimaryKeyModel'), primary_key=True), DeleteField('TestModel', 'id')]:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)
Traceback (most recent call last):
...
SimulationFailure: Cannot delete a primary key.

# Indexed field
>>> class AddIndexedDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     add_field = models.IntegerField(db_index=True, null=True)

>>> new_sig = test_proj_sig(('TestModel',AddIndexedDatabaseColumnModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'add_field', models.IntegerField, null=True, db_index=True)"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql, debug=False) #AddIndexedDatabaseColumnModel
%(AddIndexedDatabaseColumnModel)s

# Unique field.
>>> class AddUniqueDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.IntegerField(unique=True, null=True)

>>> new_sig = test_proj_sig(('TestModel',AddUniqueDatabaseColumnModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'added_field', models.IntegerField, unique=True, null=True)"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql) #AddUniqueDatabaseColumnModel
%(AddUniqueDatabaseColumnModel)s

Foreign Key field.
>>> class ForeignKeyDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.ForeignKey(AddAnchor1, null=True)

>>> new_sig = test_proj_sig(('TestModel',ForeignKeyDatabaseColumnModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'added_field', models.ForeignKey, null=True, related_model='django_evolution.AddAnchor1')"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql) #ForeignKeyDatabaseColumnModel
%(ForeignKeyDatabaseColumnModel)s

# M2M field between models with default table names.
>>> class AddM2MDatabaseTableModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.ManyToManyField(AddAnchor1)

>>> new_sig = test_proj_sig(('TestModel',AddM2MDatabaseTableModel), *anchors)
>>> new_sig['django_evolution'][AddAnchor1.__name__] = signature.create_model_sig(AddAnchor1)
>>> anchor_sig = copy.deepcopy(base_sig)
>>> anchor_sig['django_evolution'][AddAnchor1.__name__] = signature.create_model_sig(AddAnchor1)
>>> d = Diff(anchor_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'added_field', models.ManyToManyField, related_model='django_evolution.AddAnchor1')"]

>>> test_sig = copy.deepcopy(anchor_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql, cleanup=['%(AddManyToManyDatabaseTableModel_cleanup)s']) #AddManyToManyDatabaseTableModel
%(AddManyToManyDatabaseTableModel)s

# M2M field between models with non-default table names.
>>> class AddM2MNonDefaultDatabaseTableModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.ManyToManyField(AddAnchor2)

>>> new_sig = test_proj_sig(('TestModel', AddM2MNonDefaultDatabaseTableModel), *anchors)
>>> new_sig['django_evolution'][AddAnchor2.__name__] = signature.create_model_sig(AddAnchor2)
>>> anchor_sig = copy.deepcopy(base_sig)
>>> anchor_sig['django_evolution'][AddAnchor2.__name__] = signature.create_model_sig(AddAnchor2)
>>> d = Diff(anchor_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'added_field', models.ManyToManyField, related_model='django_evolution.AddAnchor2')"]

>>> test_sig = copy.deepcopy(anchor_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql, cleanup=['%(AddManyToManyNonDefaultDatabaseTableModel_cleanup)s']) #AddManyToManyNonDefaultDatabaseTableModel
%(AddManyToManyNonDefaultDatabaseTableModel)s

# M2M field between self
# Need to find a better way to do this.
>>> new_sig = copy.deepcopy(base_sig)
>>> new_sig['django_evolution']['TestModel']['fields']['added_field'] = {'field_type': models.ManyToManyField,'related_model': 'django_evolution.TestModel'}

>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'added_field', models.ManyToManyField, related_model='django_evolution.TestModel')"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql, cleanup=['%(ManyToManySelf_cleanup)s']) #ManyToManySelf
%(ManyToManySelf)s

""" % test_sql_mapping('add_field')
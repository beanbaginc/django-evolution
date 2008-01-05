from django_evolution.tests.utils import test_sql_mapping

tests = r"""
>>> from django.db import models
>>> from django.db.models.loading import cache

>>> from django_evolution.mutations import ChangeField
>>> from django_evolution.tests.utils import test_proj_sig, execute_test_sql
>>> from django_evolution.diff import Diff

>>> import copy

# Use Cases:
# Setting a null constraint
# -- without an initial value
# -- with a null initial value
# -- with a good initial value (constant)
# -- with a good initial value (callable)
# Removing a null constraint
# Invoking a no-op change field
# Changing the max_length of a character field
# -- increasing the max_length
# -- decreasing the max_length
# Renaming a column
# Changing the db_table of a many to many relationship
# Adding an index
# Removing an index
# Adding a primary key constraint
# Removing a Primary Key (Changing the primary key column)
# Adding a unique constraint
# Removing a unique constraint
# Changing more than one attribute at a time
# Redundant attributes. (Some attribute have changed, while others haven't but are specified anyway.)

# Options that apply to all fields:
# DB related options
# null
# db_column
# db_index
# db_tablespace (Ignored)
# primary_key
# unique
# db_table (only for many to many relationships)
# -- CharField
# max_length

# Non-DB options
# blank
# core
# default
# editable
# help_text
# radio_admin
# unique_for_date
# unique_for_month
# unique_for_year
# validator_list

# I don't know yet
# choices

>>> class ChangeSequenceFieldInitial(object):
...     def __init__(self, suffix):
...         self.suffix = suffix
...
...     def __call__(self):
...         from django.db import connection
...         qn = connection.ops.quote_name
...         return qn('char_field')

# Now, a useful test model we can use for evaluating diffs
>>> class ChangeAnchor1(models.Model):
...     value = models.IntegerField()

# >>> class ChangeAnchor2(models.Model):
# ...     value = models.IntegerField()
# >>> class ChangeAnchor3(models.Model):
# ...     value = models.IntegerField()
# >>> class ChangeAnchor4(models.Model):
# ...     value = models.IntegerField()

>>> class ChangeBaseModel(models.Model):
...     my_id = models.AutoField(primary_key=True)
...     alt_pk = models.IntegerField()
...     int_field = models.IntegerField(db_column='custom_db_column')
...     int_field1 = models.IntegerField(db_index=True)
...     int_field2 = models.IntegerField(db_index=False)
...     int_field3 = models.IntegerField(unique=True)
...     int_field4 = models.IntegerField(unique=False)
...     char_field = models.CharField(max_length=20)
...     char_field1 = models.CharField(max_length=25, null=True)
...     char_field2 = models.CharField(max_length=30, null=False)
...     m2m_field1 = models.ManyToManyField(ChangeAnchor1, db_table='change_field_non-default_m2m_table')
    
# >>> class CustomChangeTableModel(models.Model):
# ...     my_id = models.IntegerField(primary_key=True)
# ...     value = models.IntegerField()
# ...     alt_value = models.CharField(max_length=20)
# ...     class Meta:
# ...         db_table = 'custom_change_table_name'

# Store the base signatures
>>> anchors = [('ChangeAnchor1', ChangeAnchor1)]
>>> base_sig = test_proj_sig(('TestModel', ChangeBaseModel), *anchors)

# Register the test models with the Django app cache
>>> cache.register_models('tests', ChangeBaseModel, ChangeAnchor1)

# Setting a null constraint without an initial value
>>> class SetNotNullChangeModel(models.Model):
...     my_id = models.AutoField(primary_key=True)
...     alt_pk = models.IntegerField()
...     int_field = models.IntegerField(db_column='custom_db_column')
...     int_field1 = models.IntegerField(db_index=True)
...     int_field2 = models.IntegerField(db_index=False)
...     int_field3 = models.IntegerField(unique=True)
...     int_field4 = models.IntegerField(unique=False)
...     char_field = models.CharField(max_length=20)
...     char_field1 = models.CharField(max_length=25, null=False)
...     char_field2 = models.CharField(max_length=30, null=False)
...     m2m_field1 = models.ManyToManyField(ChangeAnchor1, db_table='change_field_non-default_m2m_table')

>>> new_sig = test_proj_sig(('TestModel', SetNotNullChangeModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print d
%(SetNotNullChangeModelDiff)s
>>> print [str(e) for e in d.evolution()['django_evolution']]
['ChangeField("TestModel", "char_field1", initial=<<USER VALUE REQUIRED>>, null=False)']

# Without an initial value
>>> evolution = [ChangeField('TestModel', 'char_field1', null=False)]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)
Traceback (most recent call last):
...
SimulationFailure: Cannot change column 'char_field1' on 'django_evolution.TestModel' without a non-null initial value.

# With a null initial value
>>> evolution = [ChangeField('TestModel', 'char_field1', null=False, initial=None)]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)
Traceback (most recent call last):
...
SimulationFailure: Cannot change column 'char_field1' on 'django_evolution.TestModel' without a non-null initial value.

# With a good initial value (constant)
>>> evolution = [ChangeField('TestModel', 'char_field1', null=False, initial="abc's xyz")]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(SetNotNullChangeModelWithConstant)s
 
# With a good initial value (callable)
>>> evolution = [ChangeField('TestModel', 'char_field1', null=False, initial=ChangeSequenceFieldInitial('SetNotNullChangeModel'))]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(SetNotNullChangeModelWithCallable)s

# Removing a null constraint
>>> class SetNullChangeModel(models.Model):
...     my_id = models.AutoField(primary_key=True)
...     alt_pk = models.IntegerField()
...     int_field = models.IntegerField(db_column='custom_db_column')
...     int_field1 = models.IntegerField(db_index=True)
...     int_field2 = models.IntegerField(db_index=False)
...     int_field3 = models.IntegerField(unique=True)
...     int_field4 = models.IntegerField(unique=False)
...     char_field = models.CharField(max_length=20)
...     char_field1 = models.CharField(max_length=25, null=True)
...     char_field2 = models.CharField(max_length=30, null=True)
...     m2m_field1 = models.ManyToManyField(ChangeAnchor1, db_table='change_field_non-default_m2m_table')

>>> new_sig = test_proj_sig(('TestModel', SetNullChangeModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print d
%(SetNullChangeModelDiff)s
>>> print [str(e) for e in d.evolution()['django_evolution']]
['ChangeField("TestModel", "char_field2", initial=None, null=True)']

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(SetNullChangeModel)s

# Removing a null constraint
>>> class NoOpChangeModel(models.Model):
...     my_id = models.AutoField(primary_key=True)
...     alt_pk = models.IntegerField()
...     int_field = models.IntegerField(db_column='custom_db_column')
...     int_field1 = models.IntegerField(db_index=True)
...     int_field2 = models.IntegerField(db_index=False)
...     int_field3 = models.IntegerField(unique=True)
...     int_field4 = models.IntegerField(unique=False)
...     char_field = models.CharField(max_length=20)
...     char_field1 = models.CharField(max_length=25, null=True)
...     char_field2 = models.CharField(max_length=30, null=False)
...     m2m_field1 = models.ManyToManyField(ChangeAnchor1, db_table='change_field_non-default_m2m_table')

>>> new_sig = test_proj_sig(('TestModel', NoOpChangeModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print d
%(NoOpChangeModelDiff)s

>>> evolution = [ChangeField('TestModel', 'char_field1', null=True)]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(NoOpChangeModel)s

>>> class IncreasingMaxLengthChangeModel(models.Model):
...     my_id = models.AutoField(primary_key=True)
...     alt_pk = models.IntegerField()
...     int_field = models.IntegerField(db_column='custom_db_column')
...     int_field1 = models.IntegerField(db_index=True)
...     int_field2 = models.IntegerField(db_index=False)
...     int_field3 = models.IntegerField(unique=True)
...     int_field4 = models.IntegerField(unique=False)
...     char_field = models.CharField(max_length=45)
...     char_field1 = models.CharField(max_length=25, null=True)
...     char_field2 = models.CharField(max_length=30, null=False)
...     m2m_field1 = models.ManyToManyField(ChangeAnchor1, db_table='change_field_non-default_m2m_table')

>>> new_sig = test_proj_sig(('TestModel', IncreasingMaxLengthChangeModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print d
%(IncreasingMaxLengthChangeModelDiff)s
>>> print [str(e) for e in d.evolution()['django_evolution']]
['ChangeField("TestModel", "char_field", initial=None, max_length=45)']

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(IncreasingMaxLengthChangeModel)s

>>> class DecreasingMaxLengthChangeModel(models.Model):
...     my_id = models.AutoField(primary_key=True)
...     alt_pk = models.IntegerField()
...     int_field = models.IntegerField(db_column='custom_db_column')
...     int_field1 = models.IntegerField(db_index=True)
...     int_field2 = models.IntegerField(db_index=False)
...     int_field3 = models.IntegerField(unique=True)
...     int_field4 = models.IntegerField(unique=False)
...     char_field = models.CharField(max_length=1)
...     char_field1 = models.CharField(max_length=25, null=True)
...     char_field2 = models.CharField(max_length=30, null=False)
...     m2m_field1 = models.ManyToManyField(ChangeAnchor1, db_table='change_field_non-default_m2m_table')

>>> new_sig = test_proj_sig(('TestModel', DecreasingMaxLengthChangeModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print d
%(DecreasingMaxLengthChangeModelDiff)s
>>> print [str(e) for e in d.evolution()['django_evolution']]
['ChangeField("TestModel", "char_field", initial=None, max_length=1)']

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(DecreasingMaxLengthChangeModel)s

>>> class DBColumnChangeModel(models.Model):
...     my_id = models.AutoField(primary_key=True)
...     alt_pk = models.IntegerField()
...     int_field = models.IntegerField(db_column='customised_db_column')
...     int_field1 = models.IntegerField(db_index=True)
...     int_field2 = models.IntegerField(db_index=False)
...     int_field3 = models.IntegerField(unique=True)
...     int_field4 = models.IntegerField(unique=False)
...     char_field = models.CharField(max_length=20)
...     char_field1 = models.CharField(max_length=25, null=True)
...     char_field2 = models.CharField(max_length=30, null=False)
...     m2m_field1 = models.ManyToManyField(ChangeAnchor1, db_table='change_field_non-default_m2m_table')

>>> new_sig = test_proj_sig(('TestModel', DBColumnChangeModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print d
%(DBColumnChangeModelDiff)s
>>> print [str(e) for e in d.evolution()['django_evolution']]
['ChangeField("TestModel", "int_field", initial=None, db_column="customised_db_column")']

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(DBColumnChangeModel)s

>>> class M2MDbTableChangeModel(models.Model):
...     my_id = models.AutoField(primary_key=True)
...     alt_pk = models.IntegerField()
...     int_field = models.IntegerField(db_column='custom_db_column')
...     int_field1 = models.IntegerField(db_index=True)
...     int_field2 = models.IntegerField(db_index=False)
...     int_field3 = models.IntegerField(unique=True)
...     int_field4 = models.IntegerField(unique=False)
...     char_field = models.CharField(max_length=20)
...     char_field1 = models.CharField(max_length=25, null=True)
...     char_field2 = models.CharField(max_length=30, null=False)
...     m2m_field1 = models.ManyToManyField(ChangeAnchor1, db_table='custom_m2m_db_table_name')

>>> new_sig = test_proj_sig(('TestModel', M2MDbTableChangeModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print d
%(M2MDbTableChangeModelDiff)s
>>> print [str(e) for e in d.evolution()['django_evolution']]
['ChangeField("TestModel", "m2m_field1", initial=None, db_table="custom_m2m_db_table_name")']

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql, cleanup=['%(M2MDbTableChangeModel_cleanup)s'])
%(M2MDbTableChangeModel)s

>>> class AddDbIndexChangeModel(models.Model):
...     my_id = models.AutoField(primary_key=True)
...     alt_pk = models.IntegerField()
...     int_field = models.IntegerField(db_column='custom_db_column')
...     int_field1 = models.IntegerField(db_index=True)
...     int_field2 = models.IntegerField(db_index=True)
...     int_field3 = models.IntegerField(unique=True)
...     int_field4 = models.IntegerField(unique=False)
...     char_field = models.CharField(max_length=20)
...     char_field1 = models.CharField(max_length=25, null=True)
...     char_field2 = models.CharField(max_length=30, null=False)
...     m2m_field1 = models.ManyToManyField(ChangeAnchor1, db_table='change_field_non-default_m2m_table')

>>> new_sig = test_proj_sig(('TestModel', AddDbIndexChangeModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print d
%(AddDbIndexChangeModelDiff)s
>>> print [str(e) for e in d.evolution()['django_evolution']]
['ChangeField("TestModel", "int_field2", initial=None, db_index=True)']

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(AddDbIndexChangeModel)s

>>> class RemoveDbIndexChangeModel(models.Model):
...     my_id = models.AutoField(primary_key=True)
...     alt_pk = models.IntegerField()
...     int_field = models.IntegerField(db_column='custom_db_column')
...     int_field1 = models.IntegerField(db_index=False)
...     int_field2 = models.IntegerField(db_index=False)
...     int_field3 = models.IntegerField(unique=True)
...     int_field4 = models.IntegerField(unique=False)
...     char_field = models.CharField(max_length=20)
...     char_field1 = models.CharField(max_length=25, null=True)
...     char_field2 = models.CharField(max_length=30, null=False)
...     m2m_field1 = models.ManyToManyField(ChangeAnchor1, db_table='change_field_non-default_m2m_table')

>>> new_sig = test_proj_sig(('TestModel', RemoveDbIndexChangeModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print d
%(RemoveDbIndexChangeModelDiff)s
>>> print [str(e) for e in d.evolution()['django_evolution']]
['ChangeField("TestModel", "int_field1", initial=None, db_index=False)']

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['django_evolution']:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(RemoveDbIndexChangeModel)s
""" % test_sql_mapping('change_field')
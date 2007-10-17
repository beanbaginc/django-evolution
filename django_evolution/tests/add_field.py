
tests = r"""

# The AddField tests will aim to test the following usecases:
# Field resulting in a new database column.
# Field resulting in a new database column with a non-default name.
# Field resulting in a new database column in a table with a non-default name.
# Primary key field.
# Indexed field
# Unique field.
# 
# Foreign Key field.
# M2M field between models with default table names.
# M2M field between models with non-default table names.

>>> from django.db import models
>>> from django_evolution.mutations import AddField
>>> from django.db import models
>>> from django_evolution.management import signature
>>> from django_evolution.management import diff
>>> from django_evolution import models as test_app
>>> from pprint import pprint
>>> import copy

>>> class AddAnchor1(models.Model):
...     value = models.IntegerField()

>>> class AddBaseModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()

>>> base_sig = {
...     'TestModel': signature.create_model_sig(AddBaseModel), 
...     '__label__': 'testapp',
...     '__version__': 1,
... }
 
>>> class CustomTableModel(models.Model):
...     value = models.IntegerField()
...     alt_value = models.CharField(max_length=20)
...     class Meta:
...         db_table = 'custom_table_name'

>>> custom_table_sig = {
...     'CustomTableModel': signature.create_model_sig(CustomTableModel), 
...     '__label__': 'testapp',
...     '__version__': 1,
... }


# Field resulting in a new database column.
>>> class AddDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.IntegerField()

>>> database_column_sig = {
...     'TestModel': signature.create_model_sig(AddDatabaseColumnModel), 
...     '__label__': 'testapp',
...     '__version__': 1,
... }

>>> d = diff.Diff(base_sig, database_column_sig)
>>> print [str(e) for e in d.evolution()]
["AddField('TestModel', 'added_field', models.IntegerField)"]

>>> sql_statements = []
>>> original_sig = copy.deepcopy(base_sig)
>>> for mutation in d.evolution():
...     sql_statements.extend(mutation.mutate(original_sig))
>>> print sql_statements
['ALTER TABLE django_evolution_addbasemodel ADD COLUMN added_field integer;']

# # Field resulting in a new database column with a non-default name.
# >>> class NonDefaultDatabaseColumnModel(models.Model):
# ...     char_field = models.CharField(max_length=20)
# ...     int_field = models.IntegerField()
# ...     add_field = models.IntegerField(db_column='non-default_column')
# 
# >>> non_default_database_column_sig = {
# ...     'TestModel': signature.create_model_sig(NonDefaultDatabaseColumnModel), 
# ...     '__label__': 'testapp',
# ...     '__version__': 1,
# ... }
# 
# >>> d = diff.Diff(base_sig, non_default_database_column_sig)
# >>> print [str(e) for e in d.evolution()]
# ["AddField('TestModel', 'add_field', models.IntegerField, db_column='non-default_column')"]
# 
# >>> sql_statements = []
# >>> original_sig = copy.deepcopy(base_sig)
# >>> for mutation in d.evolution():
# ...     sql_statements.extend(mutation.mutate(original_sig))
# >>> print sql_statements
# This should be
# ['ALTER TABLE django_evolution_addbasemodel ADD COLUMN non-default_column integer;']
# instead of
# ['ALTER TABLE django_evolution_addbasemodel ADD COLUMN add_field integer;']


# Field resulting in a new database column in a table with a non-default name.
>>> class AddDatabaseColumnCustomTableModel(models.Model):
...     value = models.IntegerField()
...     alt_value = models.CharField(max_length=20)
...     added_field = models.IntegerField()
...     class Meta:
...         db_table = 'custom_table_name'


>>> database_column_custom_table_sig = {
...     'CustomTableModel': signature.create_model_sig(AddDatabaseColumnCustomTableModel), 
...     '__label__': 'testapp',
...     '__version__': 1,
... }

>>> d = diff.Diff(custom_table_sig, database_column_custom_table_sig)
>>> print [str(e) for e in d.evolution()]
["AddField('CustomTableModel', 'added_field', models.IntegerField)"]

>>> sql_statements = []
>>> original_sig = copy.deepcopy(custom_table_sig)
>>> for mutation in d.evolution():
...     sql_statements.extend(mutation.mutate(original_sig))
>>> print sql_statements
['ALTER TABLE custom_table_name ADD COLUMN added_field integer;']

# Primary key field.
>>> class AddPrimaryKeyModel(models.Model):
...     my_primary_key = models.AutoField(primary_key=True)
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()

>>> primary_key_sig = {
...     'TestModel': signature.create_model_sig(AddPrimaryKeyModel), 
...     '__label__': 'testapp',
...     '__version__': 1,
... }

>>> d = diff.Diff(base_sig, primary_key_sig)
>>> print [str(e) for e in d.evolution()]
["AddField('TestModel', 'my_primary_key', models.AutoField, primary_key=True)", "DeleteField('TestModel', 'id')"]

>>> sql_statements = []
>>> original_sig = copy.deepcopy(base_sig)
>>> for mutation in d.evolution():
...     sql_statements.extend(mutation.mutate(original_sig))
>>> print sql_statements
['ALTER TABLE django_evolution_addbasemodel ADD COLUMN my_primary_key serial;', 'ALTER TABLE django_evolution_addbasemodel DROP COLUMN id CASCADE;']

# # Indexed field
# >>> class AddIndexedDatabaseColumnModel(models.Model):
# ...     char_field = models.CharField(max_length=20)
# ...     int_field = models.IntegerField()
# ...     add_field = models.IntegerField(db_index=True)
# 
# >>> indexed_database_column_sig = {
# ...     'TestModel': signature.create_model_sig(AddIndexedDatabaseColumnModel), 
# ...     '__label__': 'testapp',
# ...     '__version__': 1,
# ... }
# 
# >>> d = diff.Diff(base_sig, indexed_database_column_sig)
# >>> print [str(e) for e in d.evolution()]
# ["AddField('TestModel', 'add_field', models.IntegerField, db_index=True)"]
# 
# >>> sql_statements = []
# >>> original_sig = copy.deepcopy(base_sig)
# >>> for mutation in d.evolution():
# ...     sql_statements.extend(mutation.mutate(original_sig))
# >>> print sql_statements
# There should be a create index statement here.
# ['ALTER TABLE django_evolution_addbasemodel ADD COLUMN add_field integer;']

# # Unique field.
# >>> class AddUniqueDatabaseColumnModel(models.Model):
# ...     char_field = models.CharField(max_length=20)
# ...     int_field = models.IntegerField()
# ...     added_field = models.IntegerField(unique=True)
# 
# 
# >>> unique_database_column_sig = {
# ...     'TestModel': signature.create_model_sig(AddUniqueDatabaseColumnModel), 
# ...     '__label__': 'testapp',
# ...     '__version__': 1,
# ... }
# 
# >>> d = diff.Diff(base_sig, unique_database_column_sig)
# >>> print [str(e) for e in d.evolution()]
# ["AddField('TestModel', 'added_field', models.IntegerField, unique=True)"]
# 
# >>> sql_statements = []
# >>> original_sig = copy.deepcopy(base_sig)
# >>> for mutation in d.evolution():
# ...     sql_statements.extend(mutation.mutate(original_sig))
# >>> print sql_statements
# There should be some words in the following statement about the uniqueness constraint of the field.
# ['ALTER TABLE django_evolution_addbasemodel ADD COLUMN added_field integer;']

# 
# Foreign Key field.
# M2M field between models with default table names.
# M2M field between models with non-default table names.

"""
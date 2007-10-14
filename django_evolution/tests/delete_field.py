
tests = r"""
>>> from django.db import models
>>> from django_evolution.mutations import DeleteField
>>> from django_evolution.management import signature
>>> from django_evolution.management import diff
>>> from django_evolution import models as test_app
>>> from pprint import pprint
>>> import copy
 
# All Fields
# db index (ignored for now)
# db tablespace (ignored for now)
# db column
# primary key
# unique

# M2M Fields
# to field
# db table

# Model Meta
# db table
# db tablespace (ignored for now)
# unique together (ignored for now)

# Now, a useful test model we can use for evaluating diffs
>>> class DeleteAnchor1(models.Model):
...     value = models.IntegerField()
>>> class DeleteAnchor2(models.Model):
...     value = models.IntegerField()
>>> class DeleteAnchor3(models.Model):
...     value = models.IntegerField()
>>> class DeleteAnchor4(models.Model):
...     value = models.IntegerField()

>>> class DeleteBaseModel(models.Model):
...     my_id = models.AutoField(primary_key=True)
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     int_field2 = models.IntegerField(db_column='non-default_db_column')
...     int_field3 = models.IntegerField(unique=True)
...     fk_field1 = models.ForeignKey(DeleteAnchor1)
...     m2m_field1 = models.ManyToManyField(DeleteAnchor3)
...     m2m_field2 = models.ManyToManyField(DeleteAnchor4, db_table='non-default_m2m_table')

>>> base_sig = {
...     'TestModel': signature.create_model_sig(DeleteBaseModel), 
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
 
# Deleting the primary key 
# TODO: 1) Deleting of Primary Keys results in an AddField and Delete Field combination. This is wrong?
#       2) AddField implementation is incomplete so I can't complete the test.
# -- BK
>>> class PrimaryKeyModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     int_field2 = models.IntegerField(db_column='non-default_db_column')
...     int_field3 = models.IntegerField(unique=True)
...     fk_field1 = models.ForeignKey(DeleteAnchor1)
...     m2m_field1 = models.ManyToManyField(DeleteAnchor3)
...     m2m_field2 = models.ManyToManyField(DeleteAnchor4, db_table='non-default_m2m_table')


>>> primary_key_sig = {
...     'TestModel': signature.create_model_sig(PrimaryKeyModel), 
...     '__label__': 'testapp',
...     '__version__': 1,
... }

>>> d = diff.Diff(base_sig, primary_key_sig)
>>> print [str(e) for e in d.evolution()]
["AddField('TestModel', 'id', models.AutoField, primary_key=True)", "DeleteField('TestModel', 'my_id')"]

>>> sql_statements = []
>>> original_sig = copy.deepcopy(base_sig)
>>> for mutation in d.evolution():
...     sql_statements.extend(mutation.mutate(original_sig))
>>> print sql_statements
['ALTER TABLE django_evolution_deletebasemodel ADD COLUMN id serial;', 'ALTER TABLE django_evolution_deletebasemodel DROP COLUMN my_id CASCADE;']

# Deleting a default named column
>>> class DefaultNamedColumnModel(models.Model):
...     my_id = models.AutoField(primary_key=True)
...     char_field = models.CharField(max_length=20)
...     int_field2 = models.IntegerField(db_column='non-default_db_column')
...     int_field3 = models.IntegerField(unique=True)
...     fk_field1 = models.ForeignKey(DeleteAnchor1)
...     m2m_field1 = models.ManyToManyField(DeleteAnchor3)
...     m2m_field2 = models.ManyToManyField(DeleteAnchor4, db_table='non-default_m2m_table')

>>> model_sig = {
...     'TestModel': signature.create_model_sig(DefaultNamedColumnModel), 
...     '__label__': 'testapp',
...     '__version__': 1,
... }

>>> d = diff.Diff(base_sig, model_sig)
>>> print [str(e) for e in d.evolution()]
["DeleteField('TestModel', 'int_field')"]

>>> sql_statements = []
>>> original_sig = copy.deepcopy(base_sig)
>>> for mutation in d.evolution():
...     sql_statements.extend(mutation.mutate(original_sig))
>>> print sql_statements
['ALTER TABLE django_evolution_deletebasemodel DROP COLUMN int_field CASCADE;']

# Deleting a non-default named column
>>> class NonDefaultNamedColumnModel(models.Model):
...     my_id = models.AutoField(primary_key=True)
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     int_field3 = models.IntegerField(unique=True)
...     fk_field1 = models.ForeignKey(DeleteAnchor1)
...     m2m_field1 = models.ManyToManyField(DeleteAnchor3)
...     m2m_field2 = models.ManyToManyField(DeleteAnchor4, db_table='non-default_m2m_table')

>>> model_sig = {
...     'TestModel': signature.create_model_sig(NonDefaultNamedColumnModel), 
...     '__label__': 'testapp',
...     '__version__': 1,
... }

>>> d = diff.Diff(base_sig, model_sig)
>>> print [str(e) for e in d.evolution()]
["DeleteField('TestModel', 'int_field2')"]

>>> sql_statements = []
>>> original_sig = copy.deepcopy(base_sig)
>>> for mutation in d.evolution():
...     sql_statements.extend(mutation.mutate(original_sig))
>>> print sql_statements
['ALTER TABLE django_evolution_deletebasemodel DROP COLUMN non-default_db_column CASCADE;']

# Deleting a column with database constraints (unique)
# TODO: Verify that the produced SQL is actually correct
# -- BK
>>> class ConstrainedColumnModel(models.Model):
...     my_id = models.AutoField(primary_key=True)
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     int_field2 = models.IntegerField(db_column='non-default_db_column')
...     fk_field1 = models.ForeignKey(DeleteAnchor1)
...     m2m_field1 = models.ManyToManyField(DeleteAnchor3)
...     m2m_field2 = models.ManyToManyField(DeleteAnchor4, db_table='non-default_m2m_table')

>>> model_sig = {
...     'TestModel': signature.create_model_sig(ConstrainedColumnModel), 
...     '__label__': 'testapp',
...     '__version__': 1,
... }

>>> d = diff.Diff(base_sig, model_sig)
>>> print [str(e) for e in d.evolution()]
["DeleteField('TestModel', 'int_field3')"]

>>> sql_statements = []
>>> original_sig = copy.deepcopy(base_sig)
>>> for mutation in d.evolution():
...     sql_statements.extend(mutation.mutate(original_sig))
>>> print sql_statements
['ALTER TABLE django_evolution_deletebasemodel DROP COLUMN int_field3 CASCADE;']

# Deleting a default m2m
>>> class DefaultM2MModel(models.Model):
...     my_id = models.AutoField(primary_key=True)
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     int_field2 = models.IntegerField(db_column='non-default_db_column')
...     int_field3 = models.IntegerField(unique=True)
...     fk_field1 = models.ForeignKey(DeleteAnchor1)
...     m2m_field2 = models.ManyToManyField(DeleteAnchor4, db_table='non-default_m2m_table')

>>> model_sig = {
...     'TestModel': signature.create_model_sig(DefaultM2MModel), 
...     '__label__': 'testapp',
...     '__version__': 1,
... }

>>> d = diff.Diff(base_sig, model_sig)
>>> print [str(e) for e in d.evolution()]
["DeleteField('TestModel', 'm2m_field1')"]

>>> sql_statements = []
>>> original_sig = copy.deepcopy(base_sig)
>>> for mutation in d.evolution():
...     sql_statements.extend(mutation.mutate(original_sig))
>>> print sql_statements
['DROP TABLE django_evolution_deletebasemodel_m2m_field1;']

# Deleting a m2m stored in a non-default table
>>> class NonDefaultM2MModel(models.Model):
...     my_id = models.AutoField(primary_key=True)
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     int_field2 = models.IntegerField(db_column='non-default_db_column')
...     int_field3 = models.IntegerField(unique=True)
...     fk_field1 = models.ForeignKey(DeleteAnchor1)
...     m2m_field1 = models.ManyToManyField(DeleteAnchor3)

>>> model_sig = {
...     'TestModel': signature.create_model_sig(NonDefaultM2MModel), 
...     '__label__': 'testapp',
...     '__version__': 1,
... }

>>> d = diff.Diff(base_sig, model_sig)
>>> print [str(e) for e in d.evolution()]
["DeleteField('TestModel', 'm2m_field2')"]

>>> sql_statements = []
>>> original_sig = copy.deepcopy(base_sig)
>>> for mutation in d.evolution():
...     sql_statements.extend(mutation.mutate(original_sig))
>>> print sql_statements
['DROP TABLE non-default_m2m_table;']

# Delete a foreign key
>>> class DeleteForeignKeyModel(models.Model):
...     my_id = models.AutoField(primary_key=True)
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     int_field2 = models.IntegerField(db_column='non-default_db_column')
...     int_field3 = models.IntegerField(unique=True)
...     m2m_field1 = models.ManyToManyField(DeleteAnchor3)
...     m2m_field2 = models.ManyToManyField(DeleteAnchor4, db_table='non-default_m2m_table')

>>> model_sig = {
...     'TestModel': signature.create_model_sig(DeleteForeignKeyModel), 
...     '__label__': 'testapp',
...     '__version__': 1,
... }

>>> d = diff.Diff(base_sig, model_sig)
>>> print [str(e) for e in d.evolution()]
["DeleteField('TestModel', 'fk_field1')"]

>>> sql_statements = []
>>> original_sig = copy.deepcopy(base_sig)
>>> for mutation in d.evolution():
...     sql_statements.extend(mutation.mutate(original_sig))
>>> print sql_statements
['ALTER TABLE django_evolution_deletebasemodel DROP COLUMN fk_field1 CASCADE;']

# Deleting a column from a non-default table
>>> class DeleteColumnCustomTableModel(models.Model):
...     alt_value = models.CharField(max_length=20)
...     class Meta:
...         db_table = 'custom_table_name'

>>> model_sig = {
...     'CustomTableModel': signature.create_model_sig(DeleteColumnCustomTableModel), 
...     '__label__': 'testapp',
...     '__version__': 1,
... }

>>> d = diff.Diff(custom_table_sig, model_sig)
>>> print [str(e) for e in d.evolution()]
["DeleteField('CustomTableModel', 'value')"]

>>> sql_statements = []
>>> original_sig = copy.deepcopy(custom_table_sig)
>>> for mutation in d.evolution():
...     sql_statements.extend(mutation.mutate(original_sig))
>>> print sql_statements
['ALTER TABLE custom_table_name DROP COLUMN value CASCADE;']

"""
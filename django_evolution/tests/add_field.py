
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

>>> from django.db import models
>>> from django_evolution.mutations import AddField
>>> from django.db import models
>>> from django_evolution.tests.utils import test_app_sig
>>> from django_evolution.management.diff import Diff
>>> from django_evolution.management import signature
>>> from django_evolution import models as test_app
>>> from pprint import pprint
>>> import copy

>>> class AddAnchor1(models.Model):
...     value = models.IntegerField()

>>> class AddAnchor2(models.Model):
...     value = models.IntegerField()
...     class Meta:
...         db_table = 'custom_add_anchor_table'

>>> class AddBaseModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()

>>> base_sig = test_app_sig(AddBaseModel)
>>> class CustomTableModel(models.Model):
...     value = models.IntegerField()
...     alt_value = models.CharField(max_length=20)
...     class Meta:
...         db_table = 'custom_table_name'

>>> custom_table_sig = test_app_sig(CustomTableModel)

# Field resulting in a new database column.
>>> class AddDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.IntegerField()

>>> new_sig = test_app_sig(AddDatabaseColumnModel)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'added_field', models.IntegerField)"]

>>> test_sig = copy.deepcopy(base_sig)
>>> for mutation in d.evolution()['testapp']:
...     print mutation.mutate('testapp', test_sig)
...     mutation.simulate('testapp', test_sig)
['ALTER TABLE django_evolution_addbasemodel ADD COLUMN added_field integer NOT NULL;']

>>> Diff(test_sig, new_sig).is_empty()
True

# Field resulting in a new database column with a non-default name.
>>> class NonDefaultDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     add_field = models.IntegerField(db_column='non-default_column')

>>> new_sig = test_app_sig(NonDefaultDatabaseColumnModel)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'add_field', models.IntegerField, db_column='non-default_column')"]

>>> test_sig = copy.deepcopy(base_sig)
>>> for mutation in d.evolution()['testapp']:
...     print mutation.mutate('testapp', test_sig)
...     mutation.simulate('testapp', test_sig)
['ALTER TABLE django_evolution_addbasemodel ADD COLUMN non-default_column integer NOT NULL;']

>>> Diff(test_sig, new_sig).is_empty()
True

# Field resulting in a new database column in a table with a non-default name.
>>> class AddDatabaseColumnCustomTableModel(models.Model):
...     value = models.IntegerField()
...     alt_value = models.CharField(max_length=20)
...     added_field = models.IntegerField()
...     class Meta:
...         db_table = 'custom_table_name'


>>> new_sig = test_app_sig(AddDatabaseColumnCustomTableModel)
>>> d = Diff(custom_table_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'added_field', models.IntegerField)"]

>>> test_sig = copy.deepcopy(custom_table_sig)
>>> for mutation in d.evolution()['testapp']:
...     print mutation.mutate('testapp', test_sig)
...     mutation.simulate('testapp', test_sig)
['ALTER TABLE custom_table_name ADD COLUMN added_field integer NOT NULL;']

>>> Diff(test_sig, new_sig).is_empty()
True

# # Primary key field.
# RKM: prohibited by simulation
# >>> class AddPrimaryKeyModel(models.Model):
# ...     my_primary_key = models.AutoField(primary_key=True)
# ...     char_field = models.CharField(max_length=20)
# ...     int_field = models.IntegerField()
# 
# >>> new_sig = test_app_sig(AddPrimaryKeyModel)
# >>> d = Diff(base_sig, new_sig)
# >>> print [str(e) for e in d.evolution()['testapp']]
# ["AddField('TestModel', 'my_primary_key', models.AutoField, primary_key=True)", "DeleteField('TestModel', 'id')"]
# 
# >>> test_sig = copy.deepcopy(base_sig)
# >>> for mutation in d.evolution()['testapp']:
# ...     print mutation.mutate('testapp', test_sig)
# ...     mutation.simulate('testapp', test_sig)
# ['ALTER TABLE django_evolution_addbasemodel ADD COLUMN my_primary_key serial;', 'ALTER TABLE django_evolution_addbasemodel DROP COLUMN id CASCADE;']
# 
# >>> Diff(test_sig, new_sig).is_empty()
# True

# Indexed field
>>> class AddIndexedDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     add_field = models.IntegerField(db_index=True)

>>> new_sig = test_app_sig(AddIndexedDatabaseColumnModel)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'add_field', models.IntegerField, db_index=True)"]

>>> test_sig = copy.deepcopy(base_sig)
>>> for mutation in d.evolution()['testapp']:
...     print mutation.mutate('testapp', test_sig)
...     mutation.simulate('testapp', test_sig)
['ALTER TABLE django_evolution_addbasemodel ADD COLUMN add_field integer NOT NULL;', 'CREATE INDEX "django_evolution_addbasemodel_add_field" ON "django_evolution_addbasemodel" ("add_field");']

>>> Diff(test_sig, new_sig).is_empty()
True

# Unique field.
>>> class AddUniqueDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.IntegerField(unique=True)

>>> new_sig = test_app_sig(AddUniqueDatabaseColumnModel)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'added_field', models.IntegerField, unique=True)"]

>>> test_sig = copy.deepcopy(base_sig)
>>> for mutation in d.evolution()['testapp']:
...     print mutation.mutate('testapp', test_sig)
...     mutation.simulate('testapp', test_sig)
['ALTER TABLE django_evolution_addbasemodel ADD COLUMN added_field integer NOT NULL UNIQUE;']

>>> Diff(test_sig, new_sig).is_empty()
True

# Null field
>>> class NullDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.IntegerField(null=True)

>>> new_sig = test_app_sig(NullDatabaseColumnModel)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'added_field', models.IntegerField, null=True)"]

>>> test_sig = copy.deepcopy(base_sig)
>>> for mutation in d.evolution()['testapp']:
...     print mutation.mutate('testapp', test_sig)
...     mutation.simulate('testapp', test_sig)
['ALTER TABLE django_evolution_addbasemodel ADD COLUMN added_field integer NULL;']

>>> Diff(test_sig, new_sig).is_empty()
True

# Foreign Key field.
>>> class ForeignKeyDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.ForeignKey(AddAnchor1)

>>> new_sig = test_app_sig(ForeignKeyDatabaseColumnModel)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'added_field', models.ForeignKey, related_model='django_evolution.AddAnchor1')"]

>>> test_sig = copy.deepcopy(base_sig)
>>> for mutation in d.evolution()['testapp']:
...     print mutation.mutate('testapp', test_sig)
...     mutation.simulate('testapp', test_sig)
['ALTER TABLE django_evolution_addbasemodel ADD COLUMN added_field integer NOT NULL;']

>>> Diff(test_sig, new_sig).is_empty()
True

# M2M field between models with default table names.
>>> class AddM2MDatabaseTableModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.ManyToManyField(AddAnchor1)

>>> new_sig = test_app_sig(AddM2MDatabaseTableModel)
>>> new_sig['testapp'][AddAnchor1.__name__] = signature.create_model_sig(AddAnchor1)
>>> anchor_sig = copy.deepcopy(base_sig)
>>> anchor_sig['testapp'][AddAnchor1.__name__] = signature.create_model_sig(AddAnchor1)
>>> d = Diff(anchor_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'added_field', models.ManyToManyField, related_model='django_evolution.AddAnchor1')"]

>>> test_sig = copy.deepcopy(anchor_sig)
>>> for mutation in d.evolution()['testapp']:
...     print mutation.mutate('testapp', test_sig)
...     mutation.simulate('testapp', test_sig)
['CREATE TABLE "django_evolution_addbasemodel_added_field" (\n    "id" serial NOT NULL PRIMARY KEY,\n    "testmodel_id" integer NOT NULL REFERENCES "django_evolution_addbasemodel" ("id") DEFERRABLE INITIALLY DEFERRED,\n    "addanchor1_id" integer NOT NULL REFERENCES "django_evolution_addanchor1" ("id") DEFERRABLE INITIALLY DEFERRED,\n    UNIQUE ("testmodel_id", "addanchor1_id")\n)\n;']
>>> Diff(test_sig, new_sig).is_empty()
True

# M2M field between models with non-default table names.
>>> class AddM2MNonDefaultDatabaseTableModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.ManyToManyField(AddAnchor2)

>>> new_sig = test_app_sig(AddM2MNonDefaultDatabaseTableModel)
>>> new_sig['testapp'][AddAnchor2.__name__] = signature.create_model_sig(AddAnchor2)
>>> anchor_sig = copy.deepcopy(base_sig)
>>> anchor_sig['testapp'][AddAnchor2.__name__] = signature.create_model_sig(AddAnchor2)
>>> d = Diff(anchor_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'added_field', models.ManyToManyField, related_model='django_evolution.AddAnchor2')"]

>>> test_sig = copy.deepcopy(anchor_sig)
>>> for mutation in d.evolution()['testapp']:
...     print mutation.mutate('testapp', test_sig)
...     mutation.simulate('testapp', test_sig)
['CREATE TABLE "django_evolution_addbasemodel_added_field" (\n    "id" serial NOT NULL PRIMARY KEY,\n    "testmodel_id" integer NOT NULL REFERENCES "django_evolution_addbasemodel" ("id") DEFERRABLE INITIALLY DEFERRED,\n    "addanchor2_id" integer NOT NULL REFERENCES "custom_add_anchor_table" ("id") DEFERRABLE INITIALLY DEFERRED,\n    UNIQUE ("testmodel_id", "addanchor2_id")\n)\n;']
>>> Diff(test_sig, new_sig).is_empty()
True

# M2M field between self
# Need to find a better way to do this.
>>> new_sig = copy.deepcopy(base_sig)
>>> new_sig['testapp']['TestModel']['fields']['added_field'] = {'field_type': models.ManyToManyField,'related_model': 'testapp.TestModel'}

>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'added_field', models.ManyToManyField, related_model='testapp.TestModel')"]

>>> test_sig = copy.deepcopy(base_sig)
>>> for mutation in d.evolution()['testapp']:
...     print mutation.mutate('testapp', test_sig)
...     mutation.simulate('testapp', test_sig)
['CREATE TABLE "django_evolution_addbasemodel_added_field" (\n    "id" serial NOT NULL PRIMARY KEY,\n    "from_testmodel_id" integer NOT NULL REFERENCES "django_evolution_addbasemodel" ("id") DEFERRABLE INITIALLY DEFERRED,\n    "to_testmodel_id" integer NOT NULL REFERENCES "django_evolution_addbasemodel" ("id") DEFERRABLE INITIALLY DEFERRED,\n    UNIQUE ("from_testmodel_id", "to_testmodel_id")\n)\n;']
>>> Diff(test_sig, new_sig).is_empty()
True

"""
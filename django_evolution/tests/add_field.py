
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
>>> from django.db.models.loading import cache

>>> from django_evolution.mutations import AddField
>>> from django_evolution.tests.utils import test_proj_sig, execute_test_sql
>>> from django_evolution.diff import Diff
>>> from django_evolution import signature
>>> from django_evolution import models as test_app

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

>>> class CustomTableModel(models.Model):
...     value = models.IntegerField()
...     alt_value = models.CharField(max_length=20)
...     class Meta:
...         db_table = 'custom_table_name'

# Store the base signatures
>>> base_sig = test_proj_sig(AddBaseModel)
>>> custom_table_sig = test_proj_sig(CustomTableModel)

# Register the test models with the Django app cache
>>> cache.register_models('tests', CustomTableModel, AddBaseModel, AddAnchor1, AddAnchor2)

# Field resulting in a new database column.
# This fails because the new column won't allow null values, which is a problem
# if you are adding this column to an existing table with existing data.
>>> class AddDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.IntegerField()

>>> new_sig = test_proj_sig(AddDatabaseColumnModel)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'added_field', models.IntegerField)"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['testapp']:
...     test_sql.extend(mutation.mutate('testapp', test_sig))
...     mutation.simulate('testapp', test_sig)
Traceback (most recent call last):
...
SimulationFailure: Cannot create new column 'added_field' on 'testapp.TestModel' that prohibits null values

# Null field
>>> class NullDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.IntegerField(null=True)

>>> new_sig = test_proj_sig(NullDatabaseColumnModel)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'added_field', models.IntegerField, null=True)"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['testapp']:
...     test_sql.extend(mutation.mutate('testapp', test_sig))
...     mutation.simulate('testapp', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "added_field" integer NULL;

# Field resulting in a new database column with a non-default name.
>>> class NonDefaultDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     add_field = models.IntegerField(db_column='non-default_column', null=True)

>>> new_sig = test_proj_sig(NonDefaultDatabaseColumnModel)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'add_field', models.IntegerField, null=True, db_column='non-default_column')"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['testapp']:
...     test_sql.extend(mutation.mutate('testapp', test_sig))
...     mutation.simulate('testapp', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "non-default_column" integer NULL;

# Field resulting in a new database column in a table with a non-default name.
>>> class AddDatabaseColumnCustomTableModel(models.Model):
...     value = models.IntegerField()
...     alt_value = models.CharField(max_length=20)
...     added_field = models.IntegerField(null=True)
...     class Meta:
...         db_table = 'custom_table_name'


>>> new_sig = test_proj_sig(AddDatabaseColumnCustomTableModel)
>>> d = Diff(custom_table_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'added_field', models.IntegerField, null=True)"]

>>> test_sig = copy.deepcopy(custom_table_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['testapp']:
...     test_sql.extend(mutation.mutate('testapp', test_sig))
...     mutation.simulate('testapp', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
ALTER TABLE "custom_table_name" ADD COLUMN "added_field" integer NULL;

# Add Primary key field.
# Prohibited by simulation
>>> class AddPrimaryKeyModel(models.Model):
...     my_primary_key = models.AutoField(primary_key=True)
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()

>>> new_sig = test_proj_sig(AddPrimaryKeyModel)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'my_primary_key', models.AutoField, primary_key=True)", "DeleteField('TestModel', 'id')"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['testapp']:
...     test_sql.extend(mutation.mutate('testapp', test_sig))
...     mutation.simulate('testapp', test_sig)
Traceback (most recent call last):
...
SimulationFailure: Cannot create new column 'my_primary_key' on 'testapp.TestModel' that prohibits null values

# Indexed field
>>> class AddIndexedDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     add_field = models.IntegerField(db_index=True, null=True)

>>> new_sig = test_proj_sig(AddIndexedDatabaseColumnModel)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'add_field', models.IntegerField, null=True, db_index=True)"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['testapp']:
...     test_sql.extend(mutation.mutate('testapp', test_sig))
...     mutation.simulate('testapp', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "add_field" integer NULL;
CREATE INDEX "django_evolution_addbasemodel_add_field" ON "django_evolution_addbasemodel" ("add_field");

# Unique field.
>>> class AddUniqueDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.IntegerField(unique=True, null=True)

>>> new_sig = test_proj_sig(AddUniqueDatabaseColumnModel)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'added_field', models.IntegerField, unique=True, null=True)"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['testapp']:
...     test_sql.extend(mutation.mutate('testapp', test_sig))
...     mutation.simulate('testapp', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "added_field" integer NULL UNIQUE;

# Foreign Key field.
>>> class ForeignKeyDatabaseColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.ForeignKey(AddAnchor1, null=True)

>>> new_sig = test_proj_sig(ForeignKeyDatabaseColumnModel)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'added_field', models.ForeignKey, null=True, related_model='django_evolution.AddAnchor1')"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['testapp']:
...     test_sql.extend(mutation.mutate('testapp', test_sig))
...     mutation.simulate('testapp', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "added_field" integer NULL;

# M2M field between models with default table names.
>>> class AddM2MDatabaseTableModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.ManyToManyField(AddAnchor1)

>>> new_sig = test_proj_sig(AddM2MDatabaseTableModel)
>>> new_sig['testapp'][AddAnchor1.__name__] = signature.create_model_sig(AddAnchor1)
>>> anchor_sig = copy.deepcopy(base_sig)
>>> anchor_sig['testapp'][AddAnchor1.__name__] = signature.create_model_sig(AddAnchor1)
>>> d = Diff(anchor_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'added_field', models.ManyToManyField, related_model='django_evolution.AddAnchor1')"]

>>> test_sig = copy.deepcopy(anchor_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['testapp']:
...     test_sql.extend(mutation.mutate('testapp', test_sig))
...     mutation.simulate('testapp', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql, cleanup=['DROP TABLE "django_evolution_addbasemodel_added_field"'])
CREATE TABLE "django_evolution_addbasemodel_added_field" (
    "id" serial NOT NULL PRIMARY KEY,
    "testmodel_id" integer NOT NULL REFERENCES "django_evolution_addbasemodel" ("id") DEFERRABLE INITIALLY DEFERRED,
    "addanchor1_id" integer NOT NULL REFERENCES "django_evolution_addanchor1" ("id") DEFERRABLE INITIALLY DEFERRED,
    UNIQUE ("testmodel_id", "addanchor1_id")
)
;

# M2M field between models with non-default table names.
>>> class AddM2MNonDefaultDatabaseTableModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     added_field = models.ManyToManyField(AddAnchor2)

>>> new_sig = test_proj_sig(AddM2MNonDefaultDatabaseTableModel)
>>> new_sig['testapp'][AddAnchor2.__name__] = signature.create_model_sig(AddAnchor2)
>>> anchor_sig = copy.deepcopy(base_sig)
>>> anchor_sig['testapp'][AddAnchor2.__name__] = signature.create_model_sig(AddAnchor2)
>>> d = Diff(anchor_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'added_field', models.ManyToManyField, related_model='django_evolution.AddAnchor2')"]

>>> test_sig = copy.deepcopy(anchor_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['testapp']:
...     test_sql.extend(mutation.mutate('testapp', test_sig))
...     mutation.simulate('testapp', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql, cleanup=['DROP TABLE "django_evolution_addbasemodel_added_field"'])
CREATE TABLE "django_evolution_addbasemodel_added_field" (
    "id" serial NOT NULL PRIMARY KEY,
    "testmodel_id" integer NOT NULL REFERENCES "django_evolution_addbasemodel" ("id") DEFERRABLE INITIALLY DEFERRED,
    "addanchor2_id" integer NOT NULL REFERENCES "custom_add_anchor_table" ("id") DEFERRABLE INITIALLY DEFERRED,
    UNIQUE ("testmodel_id", "addanchor2_id")
)
;

# M2M field between self
# Need to find a better way to do this.
>>> new_sig = copy.deepcopy(base_sig)
>>> new_sig['testapp']['TestModel']['fields']['added_field'] = {'field_type': models.ManyToManyField,'related_model': 'testapp.TestModel'}

>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'added_field', models.ManyToManyField, related_model='testapp.TestModel')"]

>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in d.evolution()['testapp']:
...     test_sql.extend(mutation.mutate('testapp', test_sig))
...     mutation.simulate('testapp', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql, cleanup=['DROP TABLE "django_evolution_addbasemodel_added_field"'])
CREATE TABLE "django_evolution_addbasemodel_added_field" (
    "id" serial NOT NULL PRIMARY KEY,
    "from_testmodel_id" integer NOT NULL REFERENCES "django_evolution_addbasemodel" ("id") DEFERRABLE INITIALLY DEFERRED,
    "to_testmodel_id" integer NOT NULL REFERENCES "django_evolution_addbasemodel" ("id") DEFERRABLE INITIALLY DEFERRED,
    UNIQUE ("from_testmodel_id", "to_testmodel_id")
)
;

"""
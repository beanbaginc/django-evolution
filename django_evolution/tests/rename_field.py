
tests = r"""
# Rename a database column (done)
# Rename a primary key database column (done)
# Rename a foreign key database column 

# Rename a database column with a non-default name to a default name (done)
# -- Rename a database column with a non-default name to a different non-default name (done)

# Rename a database column in a non-default table (done)
# Rename an indexed database column (Is this redundant?)
# Rename a database column with null constraints (Is this redundant?)
# RenameField with a specified db_column and db_table is not allowed
# RenameField with a specified db_column for a M2MField is not allowed
# RenameField with a specified db_table for a field other than a M2MField is not allowed

# Rename a M2M database table
# Rename a M2M non-default database table

>>> from django.db import models
>>> from django.db.models.loading import cache
>>> from django_evolution.mutations import RenameField
>>> from django_evolution.tests.utils import test_proj_sig, execute_test_sql
>>> from django_evolution.diff import Diff
>>> from django_evolution import signature
>>> from django_evolution import models as test_app

>>> import copy

>>> class RenameAnchor1(models.Model):
...     value = models.IntegerField()

>>> class RenameAnchor2(models.Model):
...     value = models.IntegerField()
...     class Meta:
...         db_table = 'custom_rename_anchor_table'

>>> class RenameAnchor3(models.Model):
...     value = models.IntegerField()

>>> class RenameBaseModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     int_field_named = models.IntegerField(db_column='custom_db_col_name')
...     int_field_named_indexed = models.IntegerField(db_column='custom_db_col_name_indexed', db_index=True)
...     fk_field = models.ForeignKey(RenameAnchor1)
...     m2m_field = models.ManyToManyField(RenameAnchor2)
...     m2m_field_named = models.ManyToManyField(RenameAnchor3, db_table='non-default_db_table')

>>> class CustomRenameTableModel(models.Model):
...     value = models.IntegerField()
...     alt_value = models.CharField(max_length=20)
...     class Meta:
...         db_table = 'custom_rename_table_name'

# Store the base signatures
>>> base_sig = test_proj_sig(RenameBaseModel)
>>> custom_table_sig = test_proj_sig(CustomRenameTableModel)

# Register the test models with the Django app cache
>>> cache.register_models('tests', CustomRenameTableModel, RenameBaseModel, RenameAnchor1, RenameAnchor2, RenameAnchor3)

# Rename a database column
>>> class RenameColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     renamed_field = models.IntegerField()
...     int_field_named = models.IntegerField(db_column='custom_db_col_name')
...     int_field_named_indexed = models.IntegerField(db_column='custom_db_col_name_indexed', db_index=True)
...     fk_field = models.ForeignKey(RenameAnchor1)
...     m2m_field = models.ManyToManyField(RenameAnchor2)
...     m2m_field_named = models.ManyToManyField(RenameAnchor3, db_table='non-default_db_table')

>>> new_sig = test_proj_sig(RenameColumnModel)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'renamed_field', models.IntegerField)", "DeleteField('TestModel', 'int_field')"]

>>> evolution = [RenameField('TestModel', 'int_field', 'renamed_field')]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('testapp', test_sig))
...     mutation.simulate('testapp', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
ALTER TABLE "django_evolution_renamebasemodel" RENAME COLUMN "int_field" TO "renamed_field";

# Rename a database column
>>> class RenamePrimaryKeyColumnModel(models.Model):
...     my_pk_id = models.AutoField(primary_key=True)
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     int_field_named = models.IntegerField(db_column='custom_db_col_name')
...     int_field_named_indexed = models.IntegerField(db_column='custom_db_col_name_indexed', db_index=True)
...     fk_field = models.ForeignKey(RenameAnchor1)
...     m2m_field = models.ManyToManyField(RenameAnchor2)
...     m2m_field_named = models.ManyToManyField(RenameAnchor3, db_table='non-default_db_table')

>>> new_sig = test_proj_sig(RenamePrimaryKeyColumnModel)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'my_pk_id', models.AutoField, primary_key=True)", "DeleteField('TestModel', 'id')"]

>>> evolution = [RenameField('TestModel', 'id', 'my_pk_id')]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('testapp', test_sig))
...     mutation.simulate('testapp', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
ALTER TABLE "django_evolution_renamebasemodel" RENAME COLUMN "id" TO "my_pk_id";

# Rename a database column with a non-default name
>>> class RenameNonDefaultColumnNameModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     renamed_field = models.IntegerField(db_column='custom_db_col_name')
...     int_field_named_indexed = models.IntegerField(db_column='custom_db_col_name_indexed', db_index=True)
...     fk_field = models.ForeignKey(RenameAnchor1)
...     m2m_field = models.ManyToManyField(RenameAnchor2)
...     m2m_field_named = models.ManyToManyField(RenameAnchor3, db_table='non-default_db_table')

>>> new_sig = test_proj_sig(RenameNonDefaultColumnNameModel)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'renamed_field', models.IntegerField, db_column='custom_db_col_name')", "DeleteField('TestModel', 'int_field_named')"]

>>> evolution = [RenameField('TestModel', 'int_field_named', 'renamed_field')]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('testapp', test_sig))
...     mutation.simulate('testapp', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
ALTER TABLE "django_evolution_renamebasemodel" RENAME COLUMN "custom_db_col_name" TO "renamed_field";

# -- Rename a database column with a non-default name to a different non-default name
>>> evolution = [RenameField('TestModel', 'int_field_named', 'renamed_field', new_db_column='custom_rename_field-column')]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('testapp', test_sig))
...     mutation.simulate('testapp', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
ALTER TABLE "django_evolution_renamebasemodel" RENAME COLUMN "custom_db_col_name" TO "custom_rename_field-column";

# Rename a database column in a non-default table
# Rename a database column
>>> class RenameColumnCustomTableModel(models.Model):
...     renamed_field = models.IntegerField()
...     alt_value = models.CharField(max_length=20)
...     class Meta:
...         db_table = 'custom_rename_table_name'

>>> new_sig = test_proj_sig(RenameColumnCustomTableModel)
>>> d = Diff(custom_table_sig, new_sig)
>>> print [str(e) for e in d.evolution()['testapp']]
["AddField('TestModel', 'renamed_field', models.IntegerField)", "DeleteField('TestModel', 'value')"]

>>> evolution = [RenameField('TestModel', 'value', 'renamed_field')]
>>> test_sig = copy.deepcopy(custom_table_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('testapp', test_sig))
...     mutation.simulate('testapp', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
ALTER TABLE "custom_rename_table_name" RENAME COLUMN "value" TO "renamed_field";

"""
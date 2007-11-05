from django_evolution.tests.utils import test_sql_mapping

tests = r"""
# Rename a database column (done)
# RenameField with a specified db table for a field other than a M2MField is allowed (but will be ignored) (done)
# Rename a primary key database column (done)
# Rename a foreign key database column (done)

# Rename a database column with a non-default name to a default name (done)
# Rename a database column with a non-default name to a different non-default name (done)
# RenameField with a specified db column and db table is allowed (but one will be ignored) (done)

# Rename a database column in a non-default table (done)

# Rename an indexed database column (Redundant, Not explicitly tested)
# Rename a database column with null constraints (Redundant, Not explicitly tested)

# Rename a M2M database table (done)
# RenameField with a specified db column for a M2MField is allowed (but will be ignored) (done)
# Rename a M2M non-default database table to a default name (done)

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
>>> anchors = [('RenameAnchor1', RenameAnchor1), ('RenameAnchor2', RenameAnchor2), ('RenameAnchor3',RenameAnchor3)]
>>> base_sig = test_proj_sig(('TestModel', RenameBaseModel), *anchors)
>>> custom_table_sig = test_proj_sig(('TestModel', CustomRenameTableModel))

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

>>> new_sig = test_proj_sig(('TestModel', RenameColumnModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'renamed_field', models.IntegerField)", "DeleteField('TestModel', 'int_field')"]

>>> evolution = [RenameField('TestModel', 'int_field', 'renamed_field')]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(RenameColumnModel)s

# RenameField with a specified db table for a field other than a M2MField is allowed (but will be ignored) (done)
>>> class RenameColumnWithTableNameModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     renamed_field = models.IntegerField()
...     int_field_named = models.IntegerField(db_column='custom_db_col_name')
...     int_field_named_indexed = models.IntegerField(db_column='custom_db_col_name_indexed', db_index=True)
...     fk_field = models.ForeignKey(RenameAnchor1)
...     m2m_field = models.ManyToManyField(RenameAnchor2)
...     m2m_field_named = models.ManyToManyField(RenameAnchor3, db_table='non-default_db_table')

>>> new_sig = test_proj_sig(('TestModel',RenameColumnWithTableNameModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'renamed_field', models.IntegerField)", "DeleteField('TestModel', 'int_field')"]

>>> evolution = [RenameField('TestModel', 'int_field', 'renamed_field', db_table='ignored_db-table')]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(RenameColumnWithTableNameModel)s

# Rename a primary key database column
>>> class RenamePrimaryKeyColumnModel(models.Model):
...     my_pk_id = models.AutoField(primary_key=True)
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     int_field_named = models.IntegerField(db_column='custom_db_col_name')
...     int_field_named_indexed = models.IntegerField(db_column='custom_db_col_name_indexed', db_index=True)
...     fk_field = models.ForeignKey(RenameAnchor1)
...     m2m_field = models.ManyToManyField(RenameAnchor2)
...     m2m_field_named = models.ManyToManyField(RenameAnchor3, db_table='non-default_db_table')

>>> new_sig = test_proj_sig(('TestModel',RenamePrimaryKeyColumnModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'my_pk_id', models.AutoField, primary_key=True)", "DeleteField('TestModel', 'id')"]

>>> evolution = [RenameField('TestModel', 'id', 'my_pk_id')]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(RenamePrimaryKeyColumnModel)s

# Rename a foreign key database column 
>>> class RenameForeignKeyColumnModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     int_field_named = models.IntegerField(db_column='custom_db_col_name')
...     int_field_named_indexed = models.IntegerField(db_column='custom_db_col_name_indexed', db_index=True)
...     renamed_field = models.ForeignKey(RenameAnchor1)
...     m2m_field = models.ManyToManyField(RenameAnchor2)
...     m2m_field_named = models.ManyToManyField(RenameAnchor3, db_table='non-default_db_table')

>>> new_sig = test_proj_sig(('TestModel',RenameForeignKeyColumnModel), *anchors)
>>> base_sig = copy.deepcopy(base_sig)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'renamed_field', models.ForeignKey, related_model='django_evolution.RenameAnchor1')", "DeleteField('TestModel', 'fk_field')"]

>>> evolution = [RenameField('TestModel', 'fk_field', 'renamed_field')]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(RenameForeignKeyColumnModel)s

# Rename a database column with a non-default name
>>> class RenameNonDefaultColumnNameModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     renamed_field = models.IntegerField()
...     int_field_named_indexed = models.IntegerField(db_column='custom_db_col_name_indexed', db_index=True)
...     fk_field = models.ForeignKey(RenameAnchor1)
...     m2m_field = models.ManyToManyField(RenameAnchor2)
...     m2m_field_named = models.ManyToManyField(RenameAnchor3, db_table='non-default_db_table')

>>> new_sig = test_proj_sig(('TestModel',RenameNonDefaultColumnNameModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'renamed_field', models.IntegerField)", "DeleteField('TestModel', 'int_field_named')"]

>>> evolution = [RenameField('TestModel', 'int_field_named', 'renamed_field')]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(RenameNonDefaultColumnNameModel)s

# Rename a database column with a non-default name to a different non-default name
>>> class RenameNonDefaultColumnNameToNonDefaultNameModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     renamed_field = models.IntegerField(db_column='non-default_column_name')
...     int_field_named_indexed = models.IntegerField(db_column='custom_db_col_name_indexed', db_index=True)
...     fk_field = models.ForeignKey(RenameAnchor1)
...     m2m_field = models.ManyToManyField(RenameAnchor2)
...     m2m_field_named = models.ManyToManyField(RenameAnchor3, db_table='non-default_db_table')

>>> new_sig = test_proj_sig(('TestModel',RenameNonDefaultColumnNameToNonDefaultNameModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'renamed_field', models.IntegerField, db_column='non-default_column_name')", "DeleteField('TestModel', 'int_field_named')"]

>>> evolution = [RenameField('TestModel', 'int_field_named', 'renamed_field', db_column='non-default_column_name')]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(RenameNonDefaultColumnNameToNonDefaultNameModel)s
 
# RenameField with a specified db column and db table is allowed (but one will be ignored)
>>> class RenameNonDefaultColumnNameToNonDefaultNameAndTableModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     renamed_field = models.IntegerField(db_column='non-default_column_name2')
...     int_field_named_indexed = models.IntegerField(db_column='custom_db_col_name_indexed', db_index=True)
...     fk_field = models.ForeignKey(RenameAnchor1)
...     m2m_field = models.ManyToManyField(RenameAnchor2)
...     m2m_field_named = models.ManyToManyField(RenameAnchor3, db_table='non-default_db_table')

>>> new_sig = test_proj_sig(('TestModel',RenameNonDefaultColumnNameToNonDefaultNameAndTableModel), *anchors)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'renamed_field', models.IntegerField, db_column='non-default_column_name2')", "DeleteField('TestModel', 'int_field_named')"]

>>> evolution = [RenameField('TestModel', 'int_field_named', 'renamed_field', db_column='non-default_column_name2', db_table='custom_ignored_db-table')]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(RenameNonDefaultColumnNameToNonDefaultNameAndTableModel)s

# Rename a database column in a non-default table
# Rename a database column
>>> class RenameColumnCustomTableModel(models.Model):
...     renamed_field = models.IntegerField()
...     alt_value = models.CharField(max_length=20)
...     class Meta:
...         db_table = 'custom_rename_table_name'

>>> new_sig = test_proj_sig(('TestModel',RenameColumnCustomTableModel), *anchors)
>>> d = Diff(custom_table_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'renamed_field', models.IntegerField)", "DeleteField('TestModel', 'value')"]

>>> evolution = [RenameField('TestModel', 'value', 'renamed_field')]
>>> test_sig = copy.deepcopy(custom_table_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql)
%(RenameColumnCustomTableModel)s

# Rename a M2M database table
>>> class RenameM2MTableModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     int_field_named = models.IntegerField(db_column='custom_db_col_name')
...     int_field_named_indexed = models.IntegerField(db_column='custom_db_col_name_indexed', db_index=True)
...     fk_field = models.ForeignKey(RenameAnchor1)
...     renamed_field = models.ManyToManyField(RenameAnchor2)
...     m2m_field_named = models.ManyToManyField(RenameAnchor3, db_table='non-default_db_table')

>>> new_sig = test_proj_sig(('TestModel',RenameM2MTableModel), *anchors)
>>> base_sig = copy.deepcopy(base_sig)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'renamed_field', models.ManyToManyField, related_model='django_evolution.RenameAnchor2')", "DeleteField('TestModel', 'm2m_field')"]

>>> evolution = [RenameField('TestModel', 'm2m_field', 'renamed_field')]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True
>>> execute_test_sql(test_sql, cleanup=['%(RenameManyToManyTableModel_cleanup)s'])
%(RenameManyToManyTableModel)s

# RenameField with a specified db column for a M2MField is allowed (but will be ignored)
>>> class RenameM2MTableWithColumnNameModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     int_field_named = models.IntegerField(db_column='custom_db_col_name')
...     int_field_named_indexed = models.IntegerField(db_column='custom_db_col_name_indexed', db_index=True)
...     fk_field = models.ForeignKey(RenameAnchor1)
...     renamed_field = models.ManyToManyField(RenameAnchor2)
...     m2m_field_named = models.ManyToManyField(RenameAnchor3, db_table='non-default_db_table')

>>> new_sig = test_proj_sig(('TestModel',RenameM2MTableWithColumnNameModel), *anchors)
>>> base_sig = copy.deepcopy(base_sig)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'renamed_field', models.ManyToManyField, related_model='django_evolution.RenameAnchor2')", "DeleteField('TestModel', 'm2m_field')"]

>>> evolution = [RenameField('TestModel', 'm2m_field', 'renamed_field', db_column='ignored_db-column')]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql, cleanup=['%(RenameManyToManyTableWithColumnNameModel_cleanup)s'])
%(RenameManyToManyTableWithColumnNameModel)s

# Rename a M2M non-default database table to a default name
>>> class RenameNonDefaultM2MTableModel(models.Model):
...     char_field = models.CharField(max_length=20)
...     int_field = models.IntegerField()
...     int_field_named = models.IntegerField(db_column='custom_db_col_name')
...     int_field_named_indexed = models.IntegerField(db_column='custom_db_col_name_indexed', db_index=True)
...     fk_field = models.ForeignKey(RenameAnchor1)
...     m2m_field = models.ManyToManyField(RenameAnchor2)
...     renamed_field = models.ManyToManyField(RenameAnchor3, db_table='non-default_db_table')

>>> new_sig = test_proj_sig(('TestModel',RenameNonDefaultM2MTableModel), *anchors)
>>> base_sig = copy.deepcopy(base_sig)
>>> d = Diff(base_sig, new_sig)
>>> print [str(e) for e in d.evolution()['django_evolution']]
["AddField('TestModel', 'renamed_field', models.ManyToManyField, db_table='non-default_db_table', related_model='django_evolution.RenameAnchor3')", "DeleteField('TestModel', 'm2m_field_named')"]

>>> evolution = [RenameField('TestModel', 'm2m_field_named', 'renamed_field')]
>>> test_sig = copy.deepcopy(base_sig)
>>> test_sql = []
>>> for mutation in evolution:
...     test_sql.extend(mutation.mutate('django_evolution', test_sig))
...     mutation.simulate('django_evolution', test_sig)

>>> Diff(test_sig, new_sig).is_empty()
True

>>> execute_test_sql(test_sql, cleanup=['%(RenameNonDefaultManyToManyTableModel_cleanup)s'])
%(RenameNonDefaultManyToManyTableModel)s
""" % test_sql_mapping('rename_field')
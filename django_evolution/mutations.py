from django.conf import settings
from django.contrib.contenttypes import generic
from django.db.models.fields import *
from django.db.models.fields.related import *
from django.db import models
from django_evolution.signature import ATTRIBUTE_DEFAULTS
from django_evolution import CannotSimulate, SimulationFailure

FK_INTEGER_TYPES = ['AutoField', 'PositiveIntegerField', 'PositiveSmallIntegerField']

def get_evolution_module():
    module_name = ['django_evolution.db',settings.DATABASE_ENGINE]
    return __import__('.'.join(module_name),{},{},[''])

class BaseMutation:
    def __init__(self):
        pass
        
    def mutate(self, app_label, proj_sig):
        """
        Performs the mutation on the database. Database changes will occur 
        after this function is invoked.
        """
        raise NotImplementedError()
    
    def simulate(self, app_label, proj_sig):
        """
        Performs a simulation of the mutation to be performed. The purpose of
        the simulate function is to ensure that after all mutations have occured
        the database will emerge in a state consistent with the currently loaded
        models file.
        """
        raise NotImplementedError()
        
class SQLMutation(BaseMutation):
    def __init__(self, tag, sql, update_func=None):
        self.tag = tag
        self.sql = sql
        self.update_func = update_func
        
    def __str__(self):
        return "SQLMutation('%s')" % self.tag
    
    def simulate(self, app_label, proj_sig):    
        "SQL mutations cannot be simulated unless an update function is provided"
        if callable(self.update_func):
            self.update_func(app_label, proj_sig)
        else:
            raise CannotSimulate('Cannot simulate SQLMutations')

    def mutate(self, app_label, proj_sig):
        "The mutation of an SQL mutation returns the raw SQL"
        return self.sql
        
class DeleteField(BaseMutation):
    def __init__(self, model_name, field_name):
        self.model_name = model_name
        self.field_name = str(field_name)
    
    def __str__(self):
        return "DeleteField('%s', '%s')" % (self.model_name, self.field_name)
        
    def simulate(self, app_label, proj_sig):    
        app_sig = proj_sig[app_label]
        model_sig = app_sig[self.model_name]

        # If the field was used in the unique_together attribute, update it.
        unique_together = model_sig['meta']['unique_together']
        unique_together_list = [] 
        for ut_index in range(0, len(unique_together), 1):
            ut = unique_together[ut_index]
            unique_together_fields = []
            for field_name_index in range(0, len(ut), 1):
                field_name = ut[field_name_index]
                if not field_name == self.field_name:
                    unique_together_fields.append(field_name)
                    
            unique_together_list.append(tuple(unique_together_fields))
        model_sig['meta']['unique_together'] = tuple(unique_together_list)
        
        # Simulate the deletion of the field.
        try:
            if model_sig['fields'][self.field_name].has_key('primary_key') and model_sig['fields'][self.field_name]['primary_key']:
                raise SimulationFailure('Cannot delete a primary key.')
            else:
                field_sig = model_sig['fields'].pop(self.field_name)
        except KeyError, ke:
            raise SimulationFailure('Cannot find the field named "%s".' % self.field_name)
            
    def mutate(self, app_label, proj_sig):
        app_sig = proj_sig[app_label]
        model_sig = app_sig[self.model_name]
        field_sig = model_sig['fields'][self.field_name]
        if field_sig['field_type'] == models.ManyToManyField:
            # Deletion of the many to many field involve dropping a table
            if field_sig.has_key('db_table'):
                m2m_table = field_sig['db_table']
            else:
                m2m_table = '%s_%s' % (model_sig['meta']['db_table'], self.field_name)    
            sql_statements = get_evolution_module().delete_table(app_sig, m2m_table)
        else:
            if field_sig['field_type'] == models.ForeignKey:
                column_name =  field_sig.get('db_column', '%s_id' % self.field_name)
            else:
                column_name =  field_sig.get('db_column', self.field_name)
            table_name = app_sig[self.model_name]['meta'].get('db_table')
            sql_statements = get_evolution_module().delete_column(app_sig, table_name, column_name)
            
        return sql_statements
        
class AddField(BaseMutation):
    def __init__(self, model_name, field_name, field_type, **kwargs):
        self.model_name = model_name
        self.field_name = field_name
        self.field_type = field_type
        self.field_attrs = kwargs        
                
    def __str__(self):
        params = (self.model_name, self.field_name, self.field_type.__name__)
        str_output = ["'%s', '%s', models.%s" % params]
        for key,value in self.field_attrs.items():
            if isinstance(value, str):
                str_output.append("%s='%s'" % (key,value))
            else:
                str_output.append("%s=%s" % (key,value))
        return 'AddField(' + ', '.join(str_output) + ')'

    def simulate(self, app_label, proj_sig):    
        app_sig = proj_sig[app_label]
        model_sig = app_sig[self.model_name]        
                
        if self.field_type != models.ManyToManyField:
            if not self.field_attrs.get('null', False):
                raise SimulationFailure("Cannot create new column '%s' on '%s.%s' that prohibits null values" % (
                        self.field_name, app_label, self.model_name))
                
        model_sig['fields'][self.field_name] = {
            'field_type': self.field_type,
        }
        model_sig['fields'][self.field_name].update(self.field_attrs)

    def mutate(self, app_label, proj_sig):
        if self.field_type == models.ManyToManyField:
            return self.add_m2m_table(app_label, proj_sig)
        else:
            return self.add_column(app_label, proj_sig)
    
    def add_column(self, app_label, proj_sig):
        app_sig = proj_sig[app_label]
        evo_module = get_evolution_module()        
        column_name =  self.field_attrs.get('db_column', self.field_name)
        primary_key = self.field_attrs.get('primary_key',False)
        unique = self.field_attrs.get('unique',False)
        null = self.field_attrs.get('null',False)
        field_tablespace = self.field_attrs.get('db_tablespace',None)
        model_sig = app_sig[self.model_name]
        table_name = model_sig['meta']['db_table']
        model_tablespace = model_sig['meta'].get('db_tablespace',None)
        
        related_model = self.field_attrs.pop('related_model', None)
        if related_model:
            related_app_name, related_model_name = related_model.split('.')
            to = models.get_model(related_app_name, related_model_name)
            field = self.field_type(to, **self.field_attrs)
            self.field_attrs['related_model'] = related_model
        else:
            field = self.field_type(**self.field_attrs)
            
        sql_statements = evo_module.add_column(app_sig, 
                                               table_name, 
                                               column_name,
                                               field.db_type(),
                                               primary_key,
                                               null,
                                               unique)
        # Create SQL index if necessary
        if self.field_attrs.get('db_index', False):
            sql_statements.extend(evo_module.create_index(app_sig, 
                                                          primary_key, 
                                                          unique, 
                                                          field_tablespace, 
                                                          model_tablespace, 
                                                          table_name, 
                                                          column_name))
            
            
        return sql_statements

    def add_m2m_table(self, app_label, proj_sig):
        app_sig = proj_sig[app_label]
        evo_module = get_evolution_module()        
        model_sig = app_sig[self.model_name]
        if self.field_attrs.has_key('db_table'):
            m2m_table = self.field_attrs['db_table']
        else:
            m2m_table = '%s_%s' % (model_sig['meta']['db_table'], self.field_name)

        # If this is an m2m relation to self, avoid the inevitable name clash
        related_model = self.field_attrs['related_model']
        related_app_name, related_model_name = related_model.split('.')
        if '.'.join([app_label, self.model_name]) == related_model:
            m2m_column_name = 'from_' + self.model_name.lower() + '_id'
            m2m_reverse_name = 'to_' + related_model_name.lower() + '_id'
        else:
            m2m_column_name = self.model_name.lower() + '_id'
            m2m_reverse_name = related_model_name.lower() + '_id'
    
        model_tablespace = model_sig['meta']['db_tablespace']
        if self.field_attrs.has_key('db_tablespace'):
            field_tablespace = self.field_attrs['db_tablespace']
        else:
            field_tablespace = ATTRIBUTE_DEFAULTS['db_tablespace']
        
        auto_field_db_type = models.AutoField(primary_key=True).db_type()
        if self.field_type in FK_INTEGER_TYPES:
            fk_db_type = models.IntegerField().db_type()
        else:
            # TODO: Fix me
            fk_db_type = models.IntegerField().db_type()
            #fk_db_type = getattr(models,self.field_type)(**self.field_attrs).db_type()

        model_table = model_sig['meta']['db_table']
        model_pk_column = model_sig['meta']['pk_column']

        rel_model_sig = app_sig[related_model_name]
        
        # Refer to the way that sql_all creates the necessary sql to create the table.
        # It requires the data types of the column that it is related to. How we get this
        # in our context is unclear.
        
#        rel_model_pk_col = rel_model_sig['meta']['pk_column']
#        rel_field_sig = rel_model_sig['fields'][rel_model_pk_col]
        # FIXME
#        if rel_field_sig['field_type'] in FK_INTEGER_TYPES:
        rel_fk_db_type = models.IntegerField().db_type()
#        else:

#            rel_fk_db_type = getattr(models,rel_field_sig['field_type'])(**rel_field_sig).db_type()
        
        rel_db_table = rel_model_sig['meta']['db_table']
        rel_pk_column = rel_model_sig['meta']['pk_column']

        sql_statements = evo_module.add_table(app_sig, model_tablespace, field_tablespace,
                                              m2m_table, auto_field_db_type,
                                              m2m_column_name, m2m_reverse_name,
                                              fk_db_type, model_table, model_pk_column,
                                              rel_fk_db_type, rel_db_table, rel_pk_column)
        return sql_statements

class RenameField(BaseMutation):
    def __init__(self, model_class, old_field_name, new_field_name):
        self.model_class = model_class
        self.old_field_name = str(old_field_name)
        self.new_field_name = str(new_field_name)
        
    def __str__(self):
        return "RenameField(%s, '%s', '%s')" % (self.model_class._meta.object_name, self.old_field_name, self.new_field_name)
        
    def simulate(self, app_sig):
        model_sig = app_sig[self.model_class._meta.object_name]

        # If the field was used in the unique_together attribute, update it.
        unique_together = model_sig['meta']['unique_together']
        unique_together_list = [] 
        for ut_index in range(0, len(unique_together), 1):
            ut = unique_together[ut_index]
            unique_together_fields = []
            for field_name_index in range(0, len(ut), 1):
                field_name = ut[field_name_index]
                if field_name == self.old_field_name:
                    unique_together_fields.append(self.new_field_name)
                else:
                    unique_together_fields.append(field_name)
            unique_together_list.append(tuple(unique_together_fields))
        model_sig['meta']['unique_together'] = tuple(unique_together_list)
        
        # Update the column names
        field = self.model_class._meta.get_field(self.new_field_name)
        field_sig = model_sig['fields'][self.old_field_name]
        if not isinstance(field,(ManyToManyField)):
            old_column_name = field_sig['column']
            new_column_name = field.column
            
        # Simulate the renaming of the field.
        try:
            field = self.model_class._meta.get_field(self.new_field_name)
            field_sig = model_sig['fields'].pop(self.old_field_name)
            if isinstance(field,(ManyToManyField)):
                # Many to Many fields involve the renaming of a database table.
                field_sig['m2m_db_table'] = field.m2m_db_table()
            else:
                # All other fields involve renaming of a column only.
                field_sig['column'] = field.column
            field_sig[field.name] = field_sig
                
        except KeyError, ke:
            print 'ERROR: Cannot find the field named "%s".' % self.old_field_name
            
    def pre_mutate(self, app_sig):
        model_sig = app_sig[self.model_class._meta.object_name]
        try:
            field = self.model_class._meta.get_field(self.new_field_name)
            field_sig = model_sig['fields'][self.old_field_name]
            if isinstance(field,(ManyToManyField)):
                # Many to Many fields involve the renaming of a database table.
                self.mutate_func = self.mutate_table
                self.old_table_name = field_sig['m2m_db_table']
                self.new_table_name = field.m2m_db_table()
            else:
                # All other fields involve renaming of a column only.
                self.mutate_func = self.mutate_column
                self.old_column_name = field_sig['column']
                self.new_column_name = field.column
        except KeyError, ke:
            print 'ERROR: Cannot find the field named "%s".' % self.old_field_name
            
    def mutate(self, app_sig):
        evo_module = get_evolution_module()
        return self.mutate_func(evo_module, app_sig)
        
    def mutate_table(self, evo_module, app_sig):
        return evo_module.rename_table(app_sig, 
                                       self.old_table_name, 
                                       self.new_table_name)

    def mutate_column(self, evo_module, app_sig):
        table_data = app_sig[self.model_class._meta.object_name]
        sql_statements = evo_module.rename_column(app_sig,
                                                  self.model_class._meta.db_table,
                                                  self.old_column_name,
                                                  self.new_column_name)
        return sql_statements

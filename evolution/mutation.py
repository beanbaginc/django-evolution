from django.conf import settings
from django.db.models.fields import *
from django.db.models.fields.related import *
import copy

def get_evolution_module():
    module_name = ['django.contrib.evolution.db',settings.DATABASE_ENGINE]
    return __import__('.'.join(module_name),{},{},[''])

class BaseMutation:
    def __init__(self):
        pass
        
    def pre_mutate(self, snapshot):
        """
        Invoked before the mutate function is invoked. This function is a stub
        to be overridden by subclasses if necessary.
        """
        pass
    
    def post_mutate(self):
        """
        Invoked after the mutate function is invoked. This function is a stub
        to be overridden by subclasses if necessary.
        """
        pass
    
    def mutate(self, snapshot):
        """
        Performs the mutation on the database. Database changes will occur 
        after this function is invoked.
        """
        raise NotImplementedError()
    
    def pre_simulate(self):
        """
        Invoked before the simulate function is invoked. This function is a stub
        to be overridden by subclasses if necessary.
        """
        pass
    
    def post_simulate(self):
        """
        Invoked after the simulate function is invoked. This function is a stub
        to be overridden by subclasses if necessary.
        """
        pass
    
    def simulate(self, snapshot):
        """
        Performs a simulation of the mutation to be performed. The purpose of
        the simulate function is to ensure that after all mutations have occured
        the database will emerge in a state consistent with the currently loaded
        models file.
        """
        raise NotImplementedError()
        
        
class DeleteField(BaseMutation):
    def __init__(self, model_class, field_name):
        self.model_class = model_class
        self.field_name = str(field_name)
        
    def simulate(self, snapshot):
        field_dict = snapshot[self.model_class._meta.object_name]

        # If the field was used in the unique_together attribute, update it.
        unique_together = field_dict['unique_together']
        unique_together_list = [] 
        for ut_index in range(0, len(unique_together), 1):
            ut = unique_together[ut_index]
            unique_together_fields = []
            for field_name_index in range(0, len(ut), 1):
                field_name = ut[field_name_index]
                if not field_name == self.field_name:
                    unique_together_fields.append(field_name)
                    
            unique_together_list.append(tuple(unique_together_fields))
        field_dict['unique_together'] = tuple(unique_together_list)
        
        # Update the list of column names
        field_params = field_dict[self.field_name]
        if not 'ManyToManyField' == field_params['internal_type']:
            column_name = field_params['column']
            db_columns = field_dict['db_columns']
            db_columns.remove(column_name)
            field_dict['db_columns'] = db_columns

        # Simulate the deletion of the field.
        try:
            field_params = field_dict.pop(self.field_name)
            if field_params['primary_key']:
                    print 'Primary key deletion is not supported.'
                    # replace the data
                    field_dict[self.field_name] = field_params
                    return
        except KeyError, ke:
            print 'SIMULATE ERROR: Cannot find the field named "%s".'%self.field_name
            
    def pre_mutate(self, snapshot):
        field_dict = snapshot[self.model_class._meta.object_name]
        try:
            field_params = field_dict[self.field_name]
            internal_type = field_params['internal_type']
            if internal_type == 'ManyToManyField':
                # Deletion of the many to many field involve dropping a table
                self.manytomanytable = field_params['m2m_db_table']
                self.mutate_func = self.mutate_table
            else:
                self.column_name = field_params['column']
                self.mutate_func = self.mutate_column
        except KeyError, ke:
            print 'PRE-MUTATE ERROR: Cannot find the field named "%s".'%self.field_name
            
    def mutate(self, snapshot):
        evo_module = get_evolution_module()
        return self.mutate_func(evo_module, snapshot)
        
    def mutate_column(self, evo_module, snapshot):
        table_name = self.model_class._meta.db_table
        sql_statements = evo_module.delete_column(snapshot, 
                                                  table_name, 
                                                  self.column_name)
        table_data = snapshot[self.model_class._meta.object_name]                                                  
        db_columns = table_data['db_columns']
        db_columns.remove(self.column_name)
        table_data['db_columns'] = db_columns
        return sql_statements
        
    def mutate_table(self, evo_module, snapshot):
        sql_statements = evo_module.delete_table(snapshot, self.manytomanytable)
        table_data = snapshot.pop(self.model_class._meta.object_name)
        return sql_statements
        
class RenameField(BaseMutation):
    def __init__(self, model_class, old_field_name, new_field_name):
        self.model_class = model_class
        self.old_field_name = str(old_field_name)
        self.new_field_name = str(new_field_name)
        
    def simulate(self, snapshot):
        field_dict = snapshot[self.model_class._meta.object_name]

        # If the field was used in the unique_together attribute, update it.
        unique_together = field_dict['unique_together']
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
        field_dict['unique_together'] = tuple(unique_together_list)
        
        # Update the column names
        field = self.model_class._meta.get_field(self.new_field_name)
        field_params = field_dict[self.old_field_name]
        if not isinstance(field,(ManyToManyField)):
            old_column_name = field_params['column']
            new_column_name = field.column
            db_columns = field_dict['db_columns']
            column_index = db_columns.index(old_column_name)
            db_columns[column_index] = new_column_name
            field_dict['db_columns'] = db_columns
            
        # Simulate the renaming of the field.
        try:
            field = self.model_class._meta.get_field(self.new_field_name)
            field_params = field_dict.pop(self.old_field_name)
            if isinstance(field,(ManyToManyField)):
                # Many to Many fields involve the renaming of a database table.
                field_params['m2m_db_table']= field.m2m_db_table()
            else:
                # All other fields involve renaming of a column only.
                field_params['column'] = field.column
            field_dict[field.name] = field_params
                
        except KeyError, ke:
            print 'ERROR: Cannot find the field named "%s".'%self.old_field_name
            
    def pre_mutate(self, snapshot):
        field_dict = snapshot[self.model_class._meta.object_name]
        try:
            field = self.model_class._meta.get_field(self.new_field_name)
            field_params = field_dict[self.old_field_name]
            if isinstance(field,(ManyToManyField)):
                # Many to Many fields involve the renaming of a database table.
                self.mutate_func = self.mutate_table
                self.old_table_name = field_params['m2m_db_table']
                self.new_table_name = field.m2m_db_table()
            else:
                # All other fields involve renaming of a column only.
                self.mutate_func = self.mutate_column
                self.old_column_name = field_params['column']
                self.new_column_name = field.column
        except KeyError, ke:
            print 'ERROR: Cannot find the field named "%s".'%self.old_field_name
            
    def mutate(self, snapshot):
        evo_module = get_evolution_module()
        return self.mutate_func(evo_module, snapshot)
        
    def mutate_table(self, evo_module, snapshot):
        return evo_module.rename_table(snapshot, 
                                       self.old_table_name, 
                                       self.new_table_name,)

    def mutate_column(self, evo_module, snapshot):
        table_data = snapshot[self.model_class._meta.object_name]
        sql_statements = evo_module.rename_column(snapshot,
                                                  self.model_class._meta.db_table,
                                                  self.old_column_name,
                                                  self.new_column_name,)
        db_columns = table_data['db_columns']
        column_index = db_columns.index(self.old_column_name)
        db_columns[column_index] = self.new_column_name
        table_data['db_columns'] = db_columns
        return sql_statements

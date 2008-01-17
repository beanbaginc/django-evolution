add_field = {
    'AddNonNullNonCallableDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "added_field" integer ;',
            'UPDATE "django_evolution_addbasemodel" SET "added_field" = 1 WHERE "added_field" IS NULL;',
            'ALTER TABLE "django_evolution_addbasemodel" ALTER COLUMN "added_field" SET NOT NULL;',
        ]),
    'AddNonNullCallableDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "added_field" integer ;',
            'UPDATE "django_evolution_addbasemodel" SET "added_field" = "int_field" WHERE "added_field" IS NULL;',
            'ALTER TABLE "django_evolution_addbasemodel" ALTER COLUMN "added_field" SET NOT NULL;',
        ]),
    'AddNullColumnWithInitialDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "added_field" integer ;',
            'UPDATE "django_evolution_addbasemodel" SET "added_field" = 1 WHERE "added_field" IS NULL;',
        ]),
    'AddStringDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "added_field" varchar(10) ;',
            'UPDATE "django_evolution_addbasemodel" SET "added_field" = \'abc\\\'s xyz\' WHERE "added_field" IS NULL;',
            'ALTER TABLE "django_evolution_addbasemodel" ALTER COLUMN "added_field" SET NOT NULL;',
        ]),
    'AddDateDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "added_field" timestamp with time zone ;',
            'UPDATE "django_evolution_addbasemodel" SET "added_field" = 2007-12-13 16:42:00 WHERE "added_field" IS NULL;',
            'ALTER TABLE "django_evolution_addbasemodel" ALTER COLUMN "added_field" SET NOT NULL;',
        ]),
    'AddColumnWithDefaultDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "added_field" integer ;',
            'UPDATE "django_evolution_addbasemodel" SET "added_field" = 42 WHERE "added_field" IS NULL;',
            'ALTER TABLE "django_evolution_addbasemodel" ALTER COLUMN "added_field" SET NOT NULL;',
        ]),
    'NullDatabaseColumnModel': 
        'ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "added_field" integer NULL ;',
    'NonDefaultDatabaseColumnModel': 
        'ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "non-default_column" integer NULL ;',
    'AddDatabaseColumnCustomTableModel': 
        'ALTER TABLE "custom_table_name" ADD COLUMN "added_field" integer NULL ;',
    'AddIndexedDatabaseColumnModel': 
        '\n'.join([
            'ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "add_field" integer NULL ;',
            'CREATE INDEX "django_evolution_addbasemodel_add_field" ON "django_evolution_addbasemodel" ("add_field");'
        ]),
    'AddUniqueDatabaseColumnModel': 
        'ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "added_field" integer NULL UNIQUE;',
    'ForeignKeyDatabaseColumnModel': 
        '\n'.join([
            'ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "added_field_id" integer NULL REFERENCES "django_evolution_addanchor1" ("id")  DEFERRABLE INITIALLY DEFERRED;',
            'CREATE INDEX "django_evolution_addbasemodel_added_field_id" ON "django_evolution_addbasemodel" ("added_field_id");'
        ]),
    'AddManyToManyDatabaseTableModel': 
        '\n'.join([
            'CREATE TABLE "django_evolution_addbasemodel_added_field" (',
            '    "id" serial NOT NULL PRIMARY KEY,',
            '    "testmodel_id" integer NOT NULL REFERENCES "django_evolution_addbasemodel" ("id") DEFERRABLE INITIALLY DEFERRED,',
            '    "addanchor1_id" integer NOT NULL REFERENCES "django_evolution_addanchor1" ("id") DEFERRABLE INITIALLY DEFERRED,',
            '    UNIQUE ("testmodel_id", "addanchor1_id")',
            ')',
            ';'
        ]),
     'AddManyToManyDatabaseTableModel_cleanup': 
        'DROP TABLE "django_evolution_addbasemodel_added_field"',
     'AddManyToManyNonDefaultDatabaseTableModel': 
        '\n'.join([
            'CREATE TABLE "django_evolution_addbasemodel_added_field" (',
            '    "id" serial NOT NULL PRIMARY KEY,',
            '    "testmodel_id" integer NOT NULL REFERENCES "django_evolution_addbasemodel" ("id") DEFERRABLE INITIALLY DEFERRED,',
            '    "addanchor2_id" integer NOT NULL REFERENCES "custom_add_anchor_table" ("id") DEFERRABLE INITIALLY DEFERRED,',
            '    UNIQUE ("testmodel_id", "addanchor2_id")',
            ')',
            ';'
        ]),
     'AddManyToManyNonDefaultDatabaseTableModel_cleanup': 
        'DROP TABLE "django_evolution_addbasemodel_added_field"',
     'ManyToManySelf': 
        '\n'.join([
            'CREATE TABLE "django_evolution_addbasemodel_added_field" (',
            '    "id" serial NOT NULL PRIMARY KEY,',
            '    "from_testmodel_id" integer NOT NULL REFERENCES "django_evolution_addbasemodel" ("id") DEFERRABLE INITIALLY DEFERRED,',
            '    "to_testmodel_id" integer NOT NULL REFERENCES "django_evolution_addbasemodel" ("id") DEFERRABLE INITIALLY DEFERRED,',
            '    UNIQUE ("from_testmodel_id", "to_testmodel_id")',
            ')',
            ';'
        ]),
     'ManyToManySelf_cleanup': 
        'DROP TABLE "django_evolution_addbasemodel_added_field"',
}

delete_field = {
    'DefaultNamedColumnModel': 
        'ALTER TABLE "django_evolution_deletebasemodel" DROP COLUMN "int_field" CASCADE;',
    'NonDefaultNamedColumnModel': 
        'ALTER TABLE "django_evolution_deletebasemodel" DROP COLUMN "non-default_db_column" CASCADE;',
    'ConstrainedColumnModel': 
        'ALTER TABLE "django_evolution_deletebasemodel" DROP COLUMN "int_field3" CASCADE;',
    'DefaultManyToManyModel': 
        'DROP TABLE "django_evolution_deletebasemodel_m2m_field1";',
    'NonDefaultManyToManyModel': 
        'DROP TABLE "non-default_m2m_table";',
    'DeleteForeignKeyModel': 
        'ALTER TABLE "django_evolution_deletebasemodel" DROP COLUMN "fk_field1_id" CASCADE;',
    'DeleteColumnCustomTableModel': 
        'ALTER TABLE "custom_table_name" DROP COLUMN "value" CASCADE;',
}

change_field = {
    "SetNotNullChangeModelDiff":
        '\n'.join([
            "In model django_evolution.TestModel:",
            "    In field 'char_field1':",
            "        Property 'null' has changed",]),
    "SetNotNullChangeModelWithConstant":
        '\n'.join([
            'UPDATE "django_evolution_changebasemodel" SET "char_field1" = \'abc\\\'s xyz\' WHERE "char_field1" IS NULL;',
            'ALTER TABLE "django_evolution_changebasemodel" ALTER COLUMN "char_field1" SET NOT NULL;',
        ]),
    "SetNotNullChangeModelWithCallable":
            '\n'.join([
                'UPDATE "django_evolution_changebasemodel" SET "char_field1" = "char_field" WHERE "char_field1" IS NULL;',
                'ALTER TABLE "django_evolution_changebasemodel" ALTER COLUMN "char_field1" SET NOT NULL;',
            ]),
    "SetNullChangeModelDiff":
        '\n'.join([
            "In model django_evolution.TestModel:",
            "    In field 'char_field2':",
            "        Property 'null' has changed",]),
    "SetNullChangeModel": 'ALTER TABLE "django_evolution_changebasemodel" ALTER COLUMN "char_field2" DROP NOT NULL;',
    "NoOpChangeModelDiff": '<BLANKLINE>',
    "NoOpChangeModel": '',
    "IncreasingMaxLengthChangeModelDiff": 
        '\n'.join([
            "In model django_evolution.TestModel:",
            "    In field 'char_field':",
            "        Property 'max_length' has changed",
        ]),
    "IncreasingMaxLengthChangeModel": 'ALTER TABLE "django_evolution_changebasemodel" ALTER COLUMN "char_field" TYPE varchar(45) USING CAST("char_field" as varchar(45));',
    "DecreasingMaxLengthChangeModelDiff": 
        '\n'.join([
            "In model django_evolution.TestModel:",
            "    In field 'char_field':",
            "        Property 'max_length' has changed",
        ]),
    "DecreasingMaxLengthChangeModel": 'ALTER TABLE "django_evolution_changebasemodel" ALTER COLUMN "char_field" TYPE varchar(1) USING CAST("char_field" as varchar(1));',
    "DBColumnChangeModelDiff": 
        '\n'.join([
            "In model django_evolution.TestModel:",
            "    In field 'int_field':",
            "        Property 'db_column' has changed",
        ]),
    "DBColumnChangeModel": 'ALTER TABLE "django_evolution_changebasemodel" RENAME COLUMN "custom_db_column" TO "customised_db_column";',
    "M2MDbTableChangeModelDiff": 
        '\n'.join([
            "In model django_evolution.TestModel:",
            "    In field 'm2m_field1':",
            "        Property 'db_table' has changed",
        ]),
    "M2MDbTableChangeModel": 'ALTER TABLE "django_evolution_changebasemodel" RENAME TO "custom_m2m_db_table_name";',
    "M2MDbTableChangeModel_cleanup": 'DROP TABLE "custom_m2m_db_table_name" CASCADE;',
    "AddDbIndexChangeModelDiff": 
        '\n'.join([
            "In model django_evolution.TestModel:",
            "    In field 'int_field2':",
            "        Property 'db_index' has changed",
        ]),
    "AddDbIndexChangeModel": 'CREATE INDEX "django_evolution_changebasemodel_int_field2" ON "django_evolution_changebasemodel" ("int_field2");',
    "RemoveDbIndexChangeModelDiff": 
        '\n'.join([
            "In model django_evolution.TestModel:",
            "    In field 'int_field1':",
            "        Property 'db_index' has changed",
        ]),
    "RemoveDbIndexChangeModel": 'DROP INDEX "django_evolution_changebasemodel_int_field1";',
    "AddUniqueChangeModelDiff": 
        '\n'.join([
            "In model django_evolution.TestModel:",
            "    In field 'int_field4':",
            "        Property 'unique' has changed",
        ]),
    "AddUniqueChangeModel": 'ALTER TABLE "django_evolution_changebasemodel" ADD CONSTRAINT django_evolution_changebasemodel_int_field4_key UNIQUE("int_field4");',
    "RemoveUniqueChangeModelDiff": 
        '\n'.join([
            "In model django_evolution.TestModel:",
            "    In field 'int_field3':",
            "        Property 'unique' has changed",
        ]),
    "RemoveUniqueChangeModel": 'ALTER TABLE "django_evolution_changebasemodel" DROP CONSTRAINT django_evolution_changebasemodel_int_field3_key;',
    "MultiAttrChangeModelDiff": 
        '\n'.join([
            "In model django_evolution.TestModel:",
            "    In field 'char_field2':",
            "        Property 'null' has changed",
            "    In field 'int_field':",
            "        Property 'db_column' has changed",
            "    In field 'char_field':",
            "        Property 'max_length' has changed",
        ]),
    "MultiAttrChangeModel": 
        '\n'.join([
            'ALTER TABLE "django_evolution_changebasemodel" ALTER COLUMN "char_field2" DROP NOT NULL;',
            'ALTER TABLE "django_evolution_changebasemodel" RENAME COLUMN "custom_db_column" TO "custom_db_column2";',
            'ALTER TABLE "django_evolution_changebasemodel" ALTER COLUMN "char_field" TYPE varchar(35) USING CAST("char_field" as varchar(35));',
        ]),
    "MultiAttrSingleFieldChangeModelDiff": 
        '\n'.join([
            "In model django_evolution.TestModel:",
            "    In field 'char_field2':",
            "        Property 'max_length' has changed",
            "        Property 'null' has changed",
        ]),
    "MultiAttrSingleFieldChangeModel": 
        '\n'.join([
            'ALTER TABLE "django_evolution_changebasemodel" ALTER COLUMN "char_field2" TYPE varchar(35) USING CAST("char_field2" as varchar(35));',
            'ALTER TABLE "django_evolution_changebasemodel" ALTER COLUMN "char_field2" DROP NOT NULL;',
        ]),
    "RedundantAttrsChangeModel":
        '\n'.join([
            'ALTER TABLE "django_evolution_changebasemodel" ALTER COLUMN "char_field2" DROP NOT NULL;',
            'ALTER TABLE "django_evolution_changebasemodel" RENAME COLUMN "custom_db_column" TO "custom_db_column3";',
            'ALTER TABLE "django_evolution_changebasemodel" ALTER COLUMN "char_field" TYPE varchar(35) USING CAST("char_field" as varchar(35));',
        ]),
}

delete_model = {
    'BasicModel': 
        'DROP TABLE "django_evolution_basicmodel";',
    'BasicWithM2MModel': 
        '\n'.join([
            'DROP TABLE "django_evolution_basicwithm2mmodel_m2m";',
            'DROP TABLE "django_evolution_basicwithm2mmodel";'
        ]),
    'CustomTableModel': 
        'DROP TABLE "custom_table_name";',
    'CustomTableWithM2MModel': 
        '\n'.join([
            'DROP TABLE "another_custom_table_name_m2m";',
            'DROP TABLE "another_custom_table_name";'
        ]),
}

delete_application = {
    'DeleteApplication':
        '\n'.join([
            'DROP TABLE "django_evolution_appdeleteanchor1";',
            'DROP TABLE "django_evolution_appdeletebasemodel_anchor_m2m";',
            'DROP TABLE "django_evolution_appdeletebasemodel";',
            'DROP TABLE "app_delete_custom_add_anchor_table";',
        ]),
}

rename_field = {
    'RenameColumnModel': 
        'ALTER TABLE "django_evolution_renamebasemodel" RENAME COLUMN "int_field" TO "renamed_field";',
    'RenameColumnWithTableNameModel': 
        'ALTER TABLE "django_evolution_renamebasemodel" RENAME COLUMN "int_field" TO "renamed_field";',
    'RenamePrimaryKeyColumnModel': 
        'ALTER TABLE "django_evolution_renamebasemodel" RENAME COLUMN "id" TO "my_pk_id";',
    'RenameForeignKeyColumnModel': 
        'ALTER TABLE "django_evolution_renamebasemodel" RENAME COLUMN "fk_field_id" TO "renamed_field_id";',
    'RenameNonDefaultColumnNameModel': 
        'ALTER TABLE "django_evolution_renamebasemodel" RENAME COLUMN "custom_db_col_name" TO "renamed_field";',
    'RenameNonDefaultColumnNameToNonDefaultNameModel': 
        'ALTER TABLE "django_evolution_renamebasemodel" RENAME COLUMN "custom_db_col_name" TO "non-default_column_name";',
    'RenameNonDefaultColumnNameToNonDefaultNameAndTableModel': 
        'ALTER TABLE "django_evolution_renamebasemodel" RENAME COLUMN "custom_db_col_name" TO "non-default_column_name2";',
    'RenameColumnCustomTableModel': 
        'ALTER TABLE "custom_rename_table_name" RENAME COLUMN "value" TO "renamed_field";',
    'RenameManyToManyTableModel': 
        'ALTER TABLE "django_evolution_renamebasemodel_m2m_field" RENAME TO "django_evolution_renamebasemodel_renamed_field";',
    'RenameManyToManyTableModel_cleanup': 
        'DROP TABLE "django_evolution_renamebasemodel_renamed_field"',
    'RenameManyToManyTableWithColumnNameModel': 
        'ALTER TABLE "django_evolution_renamebasemodel_m2m_field" RENAME TO "django_evolution_renamebasemodel_renamed_field";',
    'RenameManyToManyTableWithColumnNameModel_cleanup': 
        'DROP TABLE "django_evolution_renamebasemodel_renamed_field"',
    'RenameNonDefaultManyToManyTableModel': 
        'ALTER TABLE "non-default_db_table" RENAME TO "django_evolution_renamebasemodel_renamed_field";',
    'RenameNonDefaultManyToManyTableModel_cleanup': 
        'DROP TABLE "django_evolution_renamebasemodel_renamed_field"',
}

sql_mutation = {
    'SQLMutationSequence': """[
...    SQLMutation('first-two-fields', [
...        'ALTER TABLE "django_evolution_sqlbasemodel" ADD COLUMN "added_field1" integer NULL;',
...        'ALTER TABLE "django_evolution_sqlbasemodel" ADD COLUMN "added_field2" integer NULL;'
...    ], update_first_two),
...    SQLMutation('third-field', [
...        'ALTER TABLE "django_evolution_sqlbasemodel" ADD COLUMN "added_field3" integer NULL;',
...    ], update_third)]
""",
    'SQLMutationOutput': 
        '\n'.join([
            'ALTER TABLE "django_evolution_sqlbasemodel" ADD COLUMN "added_field1" integer NULL;',
            'ALTER TABLE "django_evolution_sqlbasemodel" ADD COLUMN "added_field2" integer NULL;',
            'ALTER TABLE "django_evolution_sqlbasemodel" ADD COLUMN "added_field3" integer NULL;',
        ]),
}

add_field = {
    'AddNonNullNonCallableDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE "tests_testmodel" ADD COLUMN "added_field" integer ;',
            'UPDATE "tests_testmodel" SET "added_field" = 1 WHERE "added_field" IS NULL;',
            'ALTER TABLE "tests_testmodel" ALTER COLUMN "added_field" SET NOT NULL;',
        ]),
    'AddNonNullCallableDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE "tests_testmodel" ADD COLUMN "added_field" integer ;',
            'UPDATE "tests_testmodel" SET "added_field" = "int_field" WHERE "added_field" IS NULL;',
            'ALTER TABLE "tests_testmodel" ALTER COLUMN "added_field" SET NOT NULL;',
        ]),
    'AddNullColumnWithInitialDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE "tests_testmodel" ADD COLUMN "added_field" integer ;',
            'UPDATE "tests_testmodel" SET "added_field" = 1 WHERE "added_field" IS NULL;',
        ]),
    'AddStringDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE "tests_testmodel" ADD COLUMN "added_field" varchar(10) ;',
            'UPDATE "tests_testmodel" SET "added_field" = \'abc\\\'s xyz\' WHERE "added_field" IS NULL;',
            'ALTER TABLE "tests_testmodel" ALTER COLUMN "added_field" SET NOT NULL;',
        ]),
    'AddDateDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE "tests_testmodel" ADD COLUMN "added_field" timestamp with time zone ;',
            'UPDATE "tests_testmodel" SET "added_field" = 2007-12-13 16:42:00 WHERE "added_field" IS NULL;',
            'ALTER TABLE "tests_testmodel" ALTER COLUMN "added_field" SET NOT NULL;',
        ]),
    'AddColumnWithDefaultDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE "tests_testmodel" ADD COLUMN "added_field" integer ;',
            'UPDATE "tests_testmodel" SET "added_field" = 42 WHERE "added_field" IS NULL;',
            'ALTER TABLE "tests_testmodel" ALTER COLUMN "added_field" SET NOT NULL;',
        ]),
    'AddColumnWithEmptyStringDefaultDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE "tests_testmodel" ADD COLUMN "added_field" varchar(20) ;',
            'UPDATE "tests_testmodel" SET "added_field" = \'\' WHERE "added_field" IS NULL;',
            'ALTER TABLE "tests_testmodel" ALTER COLUMN "added_field" SET NOT NULL;',
        ]),
    'NullDatabaseColumnModel': 
        'ALTER TABLE "tests_testmodel" ADD COLUMN "added_field" integer NULL ;',
    'NonDefaultDatabaseColumnModel': 
        'ALTER TABLE "tests_testmodel" ADD COLUMN "non-default_column" integer NULL ;',
    'AddDatabaseColumnCustomTableModel': 
        'ALTER TABLE "custom_table_name" ADD COLUMN "added_field" integer NULL ;',
    'AddIndexedDatabaseColumnModel': 
        '\n'.join([
            'ALTER TABLE "tests_testmodel" ADD COLUMN "add_field" integer NULL ;',
            'CREATE INDEX "tests_testmodel_add_field" ON "tests_testmodel" ("add_field");'
        ]),
    'AddUniqueDatabaseColumnModel': 
        'ALTER TABLE "tests_testmodel" ADD COLUMN "added_field" integer NULL UNIQUE;',
    'ForeignKeyDatabaseColumnModel': 
        '\n'.join([
            'ALTER TABLE "tests_testmodel" ADD COLUMN "added_field_id" integer NULL REFERENCES "tests_addanchor1" ("id")  DEFERRABLE INITIALLY DEFERRED;',
            'CREATE INDEX "tests_testmodel_added_field_id" ON "tests_testmodel" ("added_field_id");'
        ]),
    'AddManyToManyDatabaseTableModel': 
        '\n'.join([
            'CREATE TABLE "tests_testmodel_added_field" (',
            '    "id" serial NOT NULL PRIMARY KEY,',
            '    "testmodel_id" integer NOT NULL REFERENCES "tests_testmodel" ("id") DEFERRABLE INITIALLY DEFERRED,',
            '    "addanchor1_id" integer NOT NULL REFERENCES "tests_addanchor1" ("id") DEFERRABLE INITIALLY DEFERRED,',
            '    UNIQUE ("testmodel_id", "addanchor1_id")',
            ')',
            ';'
        ]),
     'AddManyToManyNonDefaultDatabaseTableModel': 
        '\n'.join([
            'CREATE TABLE "tests_testmodel_added_field" (',
            '    "id" serial NOT NULL PRIMARY KEY,',
            '    "testmodel_id" integer NOT NULL REFERENCES "tests_testmodel" ("id") DEFERRABLE INITIALLY DEFERRED,',
            '    "addanchor2_id" integer NOT NULL REFERENCES "custom_add_anchor_table" ("id") DEFERRABLE INITIALLY DEFERRED,',
            '    UNIQUE ("testmodel_id", "addanchor2_id")',
            ')',
            ';'
        ]),
     'ManyToManySelf': 
        '\n'.join([
            'CREATE TABLE "tests_testmodel_added_field" (',
            '    "id" serial NOT NULL PRIMARY KEY,',
            '    "from_testmodel_id" integer NOT NULL REFERENCES "tests_testmodel" ("id") DEFERRABLE INITIALLY DEFERRED,',
            '    "to_testmodel_id" integer NOT NULL REFERENCES "tests_testmodel" ("id") DEFERRABLE INITIALLY DEFERRED,',
            '    UNIQUE ("from_testmodel_id", "to_testmodel_id")',
            ')',
            ';'
        ]),
}

delete_field = {
    'DefaultNamedColumnModel': 
        'ALTER TABLE "tests_testmodel" DROP COLUMN "int_field" CASCADE;',
    'NonDefaultNamedColumnModel': 
        'ALTER TABLE "tests_testmodel" DROP COLUMN "non-default_db_column" CASCADE;',
    'ConstrainedColumnModel': 
        'ALTER TABLE "tests_testmodel" DROP COLUMN "int_field3" CASCADE;',
    'DefaultManyToManyModel': 
        'DROP TABLE "tests_testmodel_m2m_field1";',
    'NonDefaultManyToManyModel': 
        'DROP TABLE "non-default_m2m_table";',
    'DeleteForeignKeyModel': 
        'ALTER TABLE "tests_testmodel" DROP COLUMN "fk_field1_id" CASCADE;',
    'DeleteColumnCustomTableModel': 
        'ALTER TABLE "custom_table_name" DROP COLUMN "value" CASCADE;',
}

change_field = {
    "SetNotNullChangeModelDiff":
        '\n'.join([
            "In model tests.TestModel:",
            "    In field 'char_field1':",
            "        Property 'null' has changed",]),
    "SetNotNullChangeModelWithConstant":
        '\n'.join([
            'UPDATE "tests_testmodel" SET "char_field1" = \'abc\\\'s xyz\' WHERE "char_field1" IS NULL;',
            'ALTER TABLE "tests_testmodel" ALTER COLUMN "char_field1" SET NOT NULL;',
        ]),
    "SetNotNullChangeModelWithCallable":
            '\n'.join([
                'UPDATE "tests_testmodel" SET "char_field1" = "char_field" WHERE "char_field1" IS NULL;',
                'ALTER TABLE "tests_testmodel" ALTER COLUMN "char_field1" SET NOT NULL;',
            ]),
    "SetNullChangeModelDiff":
        '\n'.join([
            "In model tests.TestModel:",
            "    In field 'char_field2':",
            "        Property 'null' has changed",]),
    "SetNullChangeModel": 'ALTER TABLE "tests_testmodel" ALTER COLUMN "char_field2" DROP NOT NULL;',
    "NoOpChangeModelDiff": '<BLANKLINE>',
    "NoOpChangeModel": '',
    "IncreasingMaxLengthChangeModelDiff": 
        '\n'.join([
            "In model tests.TestModel:",
            "    In field 'char_field':",
            "        Property 'max_length' has changed",
        ]),
    "IncreasingMaxLengthChangeModel": 'ALTER TABLE "tests_testmodel" ALTER COLUMN "char_field" TYPE varchar(45) USING CAST("char_field" as varchar(45));',
    "DecreasingMaxLengthChangeModelDiff": 
        '\n'.join([
            "In model tests.TestModel:",
            "    In field 'char_field':",
            "        Property 'max_length' has changed",
        ]),
    "DecreasingMaxLengthChangeModel": 'ALTER TABLE "tests_testmodel" ALTER COLUMN "char_field" TYPE varchar(1) USING CAST("char_field" as varchar(1));',
    "DBColumnChangeModelDiff": 
        '\n'.join([
            "In model tests.TestModel:",
            "    In field 'int_field':",
            "        Property 'db_column' has changed",
        ]),
    "DBColumnChangeModel": 'ALTER TABLE "tests_testmodel" RENAME COLUMN "custom_db_column" TO "customised_db_column";',
    "M2MDBTableChangeModelDiff": 
        '\n'.join([
            "In model tests.TestModel:",
            "    In field 'm2m_field1':",
            "        Property 'db_table' has changed",
        ]),
    "M2MDBTableChangeModel": 'ALTER TABLE "change_field_non-default_m2m_table" RENAME TO "custom_m2m_db_table_name";',
    "AddDBIndexChangeModelDiff": 
        '\n'.join([
            "In model tests.TestModel:",
            "    In field 'int_field2':",
            "        Property 'db_index' has changed",
        ]),
    "AddDBIndexChangeModel": 'CREATE INDEX "tests_testmodel_int_field2" ON "tests_testmodel" ("int_field2");',
    "RemoveDBIndexChangeModelDiff": 
        '\n'.join([
            "In model tests.TestModel:",
            "    In field 'int_field1':",
            "        Property 'db_index' has changed",
        ]),
    "RemoveDBIndexChangeModel": 'DROP INDEX "tests_testmodel_int_field1";',
    "AddUniqueChangeModelDiff": 
        '\n'.join([
            "In model tests.TestModel:",
            "    In field 'int_field4':",
            "        Property 'unique' has changed",
        ]),
    "AddUniqueChangeModel": 'ALTER TABLE "tests_testmodel" ADD CONSTRAINT tests_testmodel_int_field4_key UNIQUE("int_field4");',
    "RemoveUniqueChangeModelDiff": 
        '\n'.join([
            "In model tests.TestModel:",
            "    In field 'int_field3':",
            "        Property 'unique' has changed",
        ]),
    "RemoveUniqueChangeModel": 'ALTER TABLE "tests_testmodel" DROP CONSTRAINT tests_testmodel_int_field3_key;',
    "MultiAttrChangeModelDiff": 
        '\n'.join([
            "In model tests.TestModel:",
            "    In field 'char_field2':",
            "        Property 'null' has changed",
            "    In field 'int_field':",
            "        Property 'db_column' has changed",
            "    In field 'char_field':",
            "        Property 'max_length' has changed",
        ]),
    "MultiAttrChangeModel": 
        '\n'.join([
            'ALTER TABLE "tests_testmodel" ALTER COLUMN "char_field2" DROP NOT NULL;',
            'ALTER TABLE "tests_testmodel" RENAME COLUMN "custom_db_column" TO "custom_db_column2";',
            'ALTER TABLE "tests_testmodel" ALTER COLUMN "char_field" TYPE varchar(35) USING CAST("char_field" as varchar(35));',
        ]),
    "MultiAttrSingleFieldChangeModelDiff": 
        '\n'.join([
            "In model tests.TestModel:",
            "    In field 'char_field2':",
            "        Property 'max_length' has changed",
            "        Property 'null' has changed",
        ]),
    "MultiAttrSingleFieldChangeModel": 
        '\n'.join([
            'ALTER TABLE "tests_testmodel" ALTER COLUMN "char_field2" TYPE varchar(35) USING CAST("char_field2" as varchar(35));',
            'ALTER TABLE "tests_testmodel" ALTER COLUMN "char_field2" DROP NOT NULL;',
        ]),
    "RedundantAttrsChangeModel":
        '\n'.join([
            'ALTER TABLE "tests_testmodel" ALTER COLUMN "char_field2" DROP NOT NULL;',
            'ALTER TABLE "tests_testmodel" RENAME COLUMN "custom_db_column" TO "custom_db_column3";',
            'ALTER TABLE "tests_testmodel" ALTER COLUMN "char_field" TYPE varchar(35) USING CAST("char_field" as varchar(35));',
        ]),
}

delete_model = {
    'BasicModel': 
        'DROP TABLE "tests_basicmodel";',
    'BasicWithM2MModel': 
        '\n'.join([
            'DROP TABLE "tests_basicwithm2mmodel_m2m";',
            'DROP TABLE "tests_basicwithm2mmodel";'
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
            'DROP TABLE "tests_appdeleteanchor1";',
            'DROP TABLE "tests_testmodel_anchor_m2m";',
            'DROP TABLE "tests_testmodel";',
            'DROP TABLE "app_delete_custom_add_anchor_table";',
            'DROP TABLE "app_delete_custom_table_name";',
        ]),
}

rename_field = {
    'RenameColumnModel': 
        'ALTER TABLE "tests_testmodel" RENAME COLUMN "int_field" TO "renamed_field";',
    'RenameColumnWithTableNameModel': 
        'ALTER TABLE "tests_testmodel" RENAME COLUMN "int_field" TO "renamed_field";',
    'RenamePrimaryKeyColumnModel': 
        'ALTER TABLE "tests_testmodel" RENAME COLUMN "id" TO "my_pk_id";',
    'RenameForeignKeyColumnModel': 
        'ALTER TABLE "tests_testmodel" RENAME COLUMN "fk_field_id" TO "renamed_field_id";',
    'RenameNonDefaultColumnNameModel': 
        'ALTER TABLE "tests_testmodel" RENAME COLUMN "custom_db_col_name" TO "renamed_field";',
    'RenameNonDefaultColumnNameToNonDefaultNameModel': 
        'ALTER TABLE "tests_testmodel" RENAME COLUMN "custom_db_col_name" TO "non-default_column_name";',
    'RenameNonDefaultColumnNameToNonDefaultNameAndTableModel': 
        'ALTER TABLE "tests_testmodel" RENAME COLUMN "custom_db_col_name" TO "non-default_column_name2";',
    'RenameColumnCustomTableModel': 
        'ALTER TABLE "custom_rename_table_name" RENAME COLUMN "value" TO "renamed_field";',
    'RenameManyToManyTableModel': 
        'ALTER TABLE "tests_testmodel_m2m_field" RENAME TO "tests_testmodel_renamed_field";',
    'RenameManyToManyTableWithColumnNameModel': 
        'ALTER TABLE "tests_testmodel_m2m_field" RENAME TO "tests_testmodel_renamed_field";',
    'RenameNonDefaultManyToManyTableModel': 
        'ALTER TABLE "non-default_db_table" RENAME TO "tests_testmodel_renamed_field";',
}

sql_mutation = {
    'SQLMutationSequence': """[
...    SQLMutation('first-two-fields', [
...        'ALTER TABLE "tests_testmodel" ADD COLUMN "added_field1" integer NULL;',
...        'ALTER TABLE "tests_testmodel" ADD COLUMN "added_field2" integer NULL;'
...    ], update_first_two),
...    SQLMutation('third-field', [
...        'ALTER TABLE "tests_testmodel" ADD COLUMN "added_field3" integer NULL;',
...    ], update_third)]
""",
    'SQLMutationOutput': 
        '\n'.join([
            'ALTER TABLE "tests_testmodel" ADD COLUMN "added_field1" integer NULL;',
            'ALTER TABLE "tests_testmodel" ADD COLUMN "added_field2" integer NULL;',
            'ALTER TABLE "tests_testmodel" ADD COLUMN "added_field3" integer NULL;',
        ]),
}

generics = {
    'DeleteColumnModel': 'ALTER TABLE "tests_testmodel" DROP COLUMN "char_field" CASCADE;'    
}

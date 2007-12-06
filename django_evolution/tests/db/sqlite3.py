add_field = {
    'NullDatabaseColumnModel': 
        'ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "added_field" integer NULL;',
    'NonDefaultDatabaseColumnModel': 
        'ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "non-default_column" integer NULL;',
    'AddDatabaseColumnCustomTableModel': 
        'ALTER TABLE "custom_table_name" ADD COLUMN "added_field" integer NULL;',
    'AddIndexedDatabaseColumnModel': 
        '\n'.join([
            'ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "add_field" integer NULL;',
            'CREATE INDEX "django_evolution_addbasemodel_add_field" ON "django_evolution_addbasemodel" ("add_field");'
        ]),
    'AddUniqueDatabaseColumnModel': 
        '\n'.join([
            'CREATE TEMPORARY TABLE "TEMP_TABLE"("int_field" integer NOT NULL, "id" integer NOT NULL PRIMARY KEY, "char_field" varchar(20) NOT NULL, "added_field" integer NULL UNIQUE);',
            'INSERT INTO "TEMP_TABLE" SELECT "int_field", "id", "char_field", "added_field" FROM "django_evolution_addbasemodel";',
            'DROP TABLE "django_evolution_addbasemodel";',
            'CREATE TABLE "django_evolution_addbasemodel"("int_field" integer NOT NULL, "id" integer NOT NULL PRIMARY KEY, "char_field" varchar(20) NOT NULL, "added_field" integer NULL UNIQUE);',
            'INSERT INTO "django_evolution_addbasemodel" ("int_field", "id", "char_field", "added_field") SELECT "int_field", "id", "char_field", "added_field" FROM "TEMP_TABLE";',
            'DROP TABLE "TEMP_TABLE";',
        ]),
    'ForeignKeyDatabaseColumnModel': 
        '\n'.join([
            'ALTER TABLE "django_evolution_addbasemodel" ADD COLUMN "added_field_id" integer NULL REFERENCES "django_evolution_addanchor1" ("id") ;',
            'CREATE INDEX "django_evolution_addbasemodel_added_field_id" ON "django_evolution_addbasemodel" ("added_field_id");',
        ]),
    'AddManyToManyDatabaseTableModel': 
        '\n'.join([
            'CREATE TABLE "django_evolution_addbasemodel_added_field" (',
            '    "id" integer NOT NULL PRIMARY KEY,',
            '    "testmodel_id" integer NOT NULL REFERENCES "django_evolution_addbasemodel" ("id"),',
            '    "addanchor1_id" integer NOT NULL REFERENCES "django_evolution_addanchor1" ("id"),',
            '    UNIQUE ("testmodel_id", "addanchor1_id")',
            ')',
            ';',
        ]),
     'AddManyToManyDatabaseTableModel_cleanup': 
        'DROP TABLE "django_evolution_addbasemodel_added_field"',
     'AddManyToManyNonDefaultDatabaseTableModel': 
        '\n'.join([
            'CREATE TABLE "django_evolution_addbasemodel_added_field" (',
            '    "id" integer NOT NULL PRIMARY KEY,',
            '    "testmodel_id" integer NOT NULL REFERENCES "django_evolution_addbasemodel" ("id"),',
            '    "addanchor2_id" integer NOT NULL REFERENCES "custom_add_anchor_table" ("id"),',
            '    UNIQUE ("testmodel_id", "addanchor2_id")',
            ')',
            ';',
        ]),
     'AddManyToManyNonDefaultDatabaseTableModel_cleanup': 
        'DROP TABLE "django_evolution_addbasemodel_added_field"',
     'ManyToManySelf': 
        '\n'.join([
            'CREATE TABLE "django_evolution_addbasemodel_added_field" (',
            '    "id" integer NOT NULL PRIMARY KEY,',
            '    "from_testmodel_id" integer NOT NULL REFERENCES "django_evolution_addbasemodel" ("id"),',
            '    "to_testmodel_id" integer NOT NULL REFERENCES "django_evolution_addbasemodel" ("id"),',
            '    UNIQUE ("from_testmodel_id", "to_testmodel_id")',
            ')',
            ';',
        ]),
     'ManyToManySelf_cleanup': 
        'DROP TABLE "django_evolution_addbasemodel_added_field"',
}

delete_field = {
    'DefaultNamedColumnModel': 
        '\n'.join([
            'CREATE TEMPORARY TABLE "TEMP_TABLE"("non-default_db_column" integer NOT NULL, "int_field3" integer NOT NULL UNIQUE, "fk_field1_id" integer NOT NULL, "char_field" varchar(20) NOT NULL, "my_id" integer NOT NULL PRIMARY KEY);',
            'INSERT INTO "TEMP_TABLE" SELECT "non-default_db_column", "int_field3", "fk_field1_id", "char_field", "my_id" FROM "django_evolution_deletebasemodel";',
            'DROP TABLE "django_evolution_deletebasemodel";',
            'CREATE TABLE "django_evolution_deletebasemodel"("non-default_db_column" integer NOT NULL, "int_field3" integer NOT NULL UNIQUE, "fk_field1_id" integer NOT NULL, "char_field" varchar(20) NOT NULL, "my_id" integer NOT NULL PRIMARY KEY);',
            'CREATE INDEX "django_evolution_deletebasemodel_fk_field1_id" ON "django_evolution_deletebasemodel" ("fk_field1_id");',
            'INSERT INTO "django_evolution_deletebasemodel" ("non-default_db_column", "int_field3", "fk_field1_id", "char_field", "my_id") SELECT "non-default_db_column", "int_field3", "fk_field1_id", "char_field", "my_id" FROM "TEMP_TABLE";',
            'DROP TABLE "TEMP_TABLE";',
        ]),
    'NonDefaultNamedColumnModel': 
        '\n'.join([
            'CREATE TEMPORARY TABLE "TEMP_TABLE"("int_field" integer NOT NULL, "int_field3" integer NOT NULL UNIQUE, "fk_field1_id" integer NOT NULL, "char_field" varchar(20) NOT NULL, "my_id" integer NOT NULL PRIMARY KEY);',
            'INSERT INTO "TEMP_TABLE" SELECT "int_field", "int_field3", "fk_field1_id", "char_field", "my_id" FROM "django_evolution_deletebasemodel";',
            'DROP TABLE "django_evolution_deletebasemodel";',
            'CREATE TABLE "django_evolution_deletebasemodel"("int_field" integer NOT NULL, "int_field3" integer NOT NULL UNIQUE, "fk_field1_id" integer NOT NULL, "char_field" varchar(20) NOT NULL, "my_id" integer NOT NULL PRIMARY KEY);',
            'CREATE INDEX "django_evolution_deletebasemodel_fk_field1_id" ON "django_evolution_deletebasemodel" ("fk_field1_id");',
            'INSERT INTO "django_evolution_deletebasemodel" ("int_field", "int_field3", "fk_field1_id", "char_field", "my_id") SELECT "int_field", "int_field3", "fk_field1_id", "char_field", "my_id" FROM "TEMP_TABLE";',
            'DROP TABLE "TEMP_TABLE";',
        ]),
    'ConstrainedColumnModel': 
        '\n'.join([
            'CREATE TEMPORARY TABLE "TEMP_TABLE"("int_field" integer NOT NULL, "non-default_db_column" integer NOT NULL, "fk_field1_id" integer NOT NULL, "char_field" varchar(20) NOT NULL, "my_id" integer NOT NULL PRIMARY KEY);',
            'INSERT INTO "TEMP_TABLE" SELECT "int_field", "non-default_db_column", "fk_field1_id", "char_field", "my_id" FROM "django_evolution_deletebasemodel";',
            'DROP TABLE "django_evolution_deletebasemodel";',
            'CREATE TABLE "django_evolution_deletebasemodel"("int_field" integer NOT NULL, "non-default_db_column" integer NOT NULL, "fk_field1_id" integer NOT NULL, "char_field" varchar(20) NOT NULL, "my_id" integer NOT NULL PRIMARY KEY);',
            'CREATE INDEX "django_evolution_deletebasemodel_fk_field1_id" ON "django_evolution_deletebasemodel" ("fk_field1_id");',
            'INSERT INTO "django_evolution_deletebasemodel" ("int_field", "non-default_db_column", "fk_field1_id", "char_field", "my_id") SELECT "int_field", "non-default_db_column", "fk_field1_id", "char_field", "my_id" FROM "TEMP_TABLE";',
            'DROP TABLE "TEMP_TABLE";',
        ]),
    'DefaultManyToManyModel': 
        'DROP TABLE "django_evolution_deletebasemodel_m2m_field1";',
    'NonDefaultManyToManyModel': 
        'DROP TABLE "non-default_m2m_table";',
    'DeleteForeignKeyModel': 
        '\n'.join([
            'CREATE TEMPORARY TABLE "TEMP_TABLE"("int_field" integer NOT NULL, "non-default_db_column" integer NOT NULL, "int_field3" integer NOT NULL UNIQUE, "char_field" varchar(20) NOT NULL, "my_id" integer NOT NULL PRIMARY KEY);',
            'INSERT INTO "TEMP_TABLE" SELECT "int_field", "non-default_db_column", "int_field3", "char_field", "my_id" FROM "django_evolution_deletebasemodel";',
            'DROP TABLE "django_evolution_deletebasemodel";',
            'CREATE TABLE "django_evolution_deletebasemodel"("int_field" integer NOT NULL, "non-default_db_column" integer NOT NULL, "int_field3" integer NOT NULL UNIQUE, "char_field" varchar(20) NOT NULL, "my_id" integer NOT NULL PRIMARY KEY);',
            'INSERT INTO "django_evolution_deletebasemodel" ("int_field", "non-default_db_column", "int_field3", "char_field", "my_id") SELECT "int_field", "non-default_db_column", "int_field3", "char_field", "my_id" FROM "TEMP_TABLE";',
            'DROP TABLE "TEMP_TABLE";',
        ]),
    'DeleteColumnCustomTableModel': 
        '\n'.join([
            'CREATE TEMPORARY TABLE "TEMP_TABLE"("id" integer NOT NULL PRIMARY KEY, "alt_value" varchar(20) NOT NULL);',
            'INSERT INTO "TEMP_TABLE" SELECT "id", "alt_value" FROM "custom_table_name";',
            'DROP TABLE "custom_table_name";',
            'CREATE TABLE "custom_table_name"("id" integer NOT NULL PRIMARY KEY, "alt_value" varchar(20) NOT NULL);',
            'INSERT INTO "custom_table_name" ("id", "alt_value") SELECT "id", "alt_value" FROM "TEMP_TABLE";',
            'DROP TABLE "TEMP_TABLE";',
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

rename_field = {
    'RenameColumnModel': 
        '\n'.join([
            'CREATE TEMPORARY TABLE "TEMP_TABLE"("custom_db_col_name" integer NOT NULL, "char_field" varchar(20) NOT NULL, "renamed_field" integer NOT NULL, "custom_db_col_name_indexed" integer NOT NULL, "fk_field_id" integer NOT NULL, "id" integer NOT NULL PRIMARY KEY);',
            'INSERT INTO "TEMP_TABLE" SELECT "custom_db_col_name", "char_field", "int_field", "custom_db_col_name_indexed", "fk_field_id", "id" FROM "django_evolution_renamebasemodel";',
            'DROP TABLE "django_evolution_renamebasemodel";',
            'CREATE TABLE "django_evolution_renamebasemodel"("custom_db_col_name" integer NOT NULL, "char_field" varchar(20) NOT NULL, "renamed_field" integer NOT NULL, "custom_db_col_name_indexed" integer NOT NULL, "fk_field_id" integer NOT NULL, "id" integer NOT NULL PRIMARY KEY);',
            'CREATE INDEX "django_evolution_renamebasemodel_custom_db_col_name_indexed" ON "django_evolution_renamebasemodel" ("custom_db_col_name_indexed");',
            'CREATE INDEX "django_evolution_renamebasemodel_fk_field_id" ON "django_evolution_renamebasemodel" ("fk_field_id");',
            'INSERT INTO "django_evolution_renamebasemodel" ("custom_db_col_name", "char_field", "renamed_field", "custom_db_col_name_indexed", "fk_field_id", "id") SELECT "custom_db_col_name", "char_field", "renamed_field", "custom_db_col_name_indexed", "fk_field_id", "id" FROM "TEMP_TABLE";',
            'DROP TABLE "TEMP_TABLE";',
        ]),
    'RenameColumnWithTableNameModel': 
        '\n'.join([
            'CREATE TEMPORARY TABLE "TEMP_TABLE"("custom_db_col_name" integer NOT NULL, "char_field" varchar(20) NOT NULL, "renamed_field" integer NOT NULL, "custom_db_col_name_indexed" integer NOT NULL, "fk_field_id" integer NOT NULL, "id" integer NOT NULL PRIMARY KEY);',
            'INSERT INTO "TEMP_TABLE" SELECT "custom_db_col_name", "char_field", "int_field", "custom_db_col_name_indexed", "fk_field_id", "id" FROM "django_evolution_renamebasemodel";',
            'DROP TABLE "django_evolution_renamebasemodel";',
            'CREATE TABLE "django_evolution_renamebasemodel"("custom_db_col_name" integer NOT NULL, "char_field" varchar(20) NOT NULL, "renamed_field" integer NOT NULL, "custom_db_col_name_indexed" integer NOT NULL, "fk_field_id" integer NOT NULL, "id" integer NOT NULL PRIMARY KEY);',
            'CREATE INDEX "django_evolution_renamebasemodel_custom_db_col_name_indexed" ON "django_evolution_renamebasemodel" ("custom_db_col_name_indexed");',
            'CREATE INDEX "django_evolution_renamebasemodel_fk_field_id" ON "django_evolution_renamebasemodel" ("fk_field_id");',
            'INSERT INTO "django_evolution_renamebasemodel" ("custom_db_col_name", "char_field", "renamed_field", "custom_db_col_name_indexed", "fk_field_id", "id") SELECT "custom_db_col_name", "char_field", "renamed_field", "custom_db_col_name_indexed", "fk_field_id", "id" FROM "TEMP_TABLE";',
            'DROP TABLE "TEMP_TABLE";',
        ]),
    'RenamePrimaryKeyColumnModel': 
        '\n'.join([
            'CREATE TEMPORARY TABLE "TEMP_TABLE"("custom_db_col_name" integer NOT NULL, "char_field" varchar(20) NOT NULL, "int_field" integer NOT NULL, "custom_db_col_name_indexed" integer NOT NULL, "fk_field_id" integer NOT NULL, "my_pk_id" integer NOT NULL PRIMARY KEY);',
            'INSERT INTO "TEMP_TABLE" SELECT "custom_db_col_name", "char_field", "int_field", "custom_db_col_name_indexed", "fk_field_id", "id" FROM "django_evolution_renamebasemodel";',
            'DROP TABLE "django_evolution_renamebasemodel";',
            'CREATE TABLE "django_evolution_renamebasemodel"("custom_db_col_name" integer NOT NULL, "char_field" varchar(20) NOT NULL, "int_field" integer NOT NULL, "custom_db_col_name_indexed" integer NOT NULL, "fk_field_id" integer NOT NULL, "my_pk_id" integer NOT NULL PRIMARY KEY);',
            'CREATE INDEX "django_evolution_renamebasemodel_custom_db_col_name_indexed" ON "django_evolution_renamebasemodel" ("custom_db_col_name_indexed");',
            'CREATE INDEX "django_evolution_renamebasemodel_fk_field_id" ON "django_evolution_renamebasemodel" ("fk_field_id");',
            'INSERT INTO "django_evolution_renamebasemodel" ("custom_db_col_name", "char_field", "int_field", "custom_db_col_name_indexed", "fk_field_id", "my_pk_id") SELECT "custom_db_col_name", "char_field", "int_field", "custom_db_col_name_indexed", "fk_field_id", "my_pk_id" FROM "TEMP_TABLE";',
            'DROP TABLE "TEMP_TABLE";',
        ]),        
    'RenameForeignKeyColumnModel': 
        '\n'.join([
            'CREATE TEMPORARY TABLE "TEMP_TABLE"("int_field" integer NOT NULL, "char_field" varchar(20) NOT NULL, "custom_db_col_name" integer NOT NULL, "custom_db_col_name_indexed" integer NOT NULL, "renamed_field_id" integer NOT NULL, "id" integer NOT NULL PRIMARY KEY);',
            'INSERT INTO "TEMP_TABLE" SELECT "int_field", "char_field", "custom_db_col_name", "custom_db_col_name_indexed", "fk_field_id", "id" FROM "django_evolution_renamebasemodel";',
            'DROP TABLE "django_evolution_renamebasemodel";',
            'CREATE TABLE "django_evolution_renamebasemodel"("int_field" integer NOT NULL, "char_field" varchar(20) NOT NULL, "custom_db_col_name" integer NOT NULL, "custom_db_col_name_indexed" integer NOT NULL, "renamed_field_id" integer NOT NULL, "id" integer NOT NULL PRIMARY KEY);',
            'CREATE INDEX "django_evolution_renamebasemodel_custom_db_col_name_indexed" ON "django_evolution_renamebasemodel" ("custom_db_col_name_indexed");',
            'CREATE INDEX "django_evolution_renamebasemodel_renamed_field_id" ON "django_evolution_renamebasemodel" ("renamed_field_id");',
            'INSERT INTO "django_evolution_renamebasemodel" ("int_field", "char_field", "custom_db_col_name", "custom_db_col_name_indexed", "renamed_field_id", "id") SELECT "int_field", "char_field", "custom_db_col_name", "custom_db_col_name_indexed", "renamed_field_id", "id" FROM "TEMP_TABLE";',
            'DROP TABLE "TEMP_TABLE";',
        ]),
    'RenameNonDefaultColumnNameModel': 
        '\n'.join([
            'CREATE TEMPORARY TABLE "TEMP_TABLE"("int_field" integer NOT NULL, "char_field" varchar(20) NOT NULL, "renamed_field" integer NOT NULL, "custom_db_col_name_indexed" integer NOT NULL, "fk_field_id" integer NOT NULL, "id" integer NOT NULL PRIMARY KEY);',
            'INSERT INTO "TEMP_TABLE" SELECT "int_field", "char_field", "custom_db_col_name", "custom_db_col_name_indexed", "fk_field_id", "id" FROM "django_evolution_renamebasemodel";',
            'DROP TABLE "django_evolution_renamebasemodel";',
            'CREATE TABLE "django_evolution_renamebasemodel"("int_field" integer NOT NULL, "char_field" varchar(20) NOT NULL, "renamed_field" integer NOT NULL, "custom_db_col_name_indexed" integer NOT NULL, "fk_field_id" integer NOT NULL, "id" integer NOT NULL PRIMARY KEY);',
            'CREATE INDEX "django_evolution_renamebasemodel_custom_db_col_name_indexed" ON "django_evolution_renamebasemodel" ("custom_db_col_name_indexed");',
            'CREATE INDEX "django_evolution_renamebasemodel_fk_field_id" ON "django_evolution_renamebasemodel" ("fk_field_id");',
            'INSERT INTO "django_evolution_renamebasemodel" ("int_field", "char_field", "renamed_field", "custom_db_col_name_indexed", "fk_field_id", "id") SELECT "int_field", "char_field", "renamed_field", "custom_db_col_name_indexed", "fk_field_id", "id" FROM "TEMP_TABLE";',
            'DROP TABLE "TEMP_TABLE";',
        ]),
    'RenameNonDefaultColumnNameToNonDefaultNameModel': 
        '\n'.join([
            'CREATE TEMPORARY TABLE "TEMP_TABLE"("int_field" integer NOT NULL, "char_field" varchar(20) NOT NULL, "non-default_column_name" integer NOT NULL, "custom_db_col_name_indexed" integer NOT NULL, "fk_field_id" integer NOT NULL, "id" integer NOT NULL PRIMARY KEY);',
            'INSERT INTO "TEMP_TABLE" SELECT "int_field", "char_field", "custom_db_col_name", "custom_db_col_name_indexed", "fk_field_id", "id" FROM "django_evolution_renamebasemodel";',
            'DROP TABLE "django_evolution_renamebasemodel";',
            'CREATE TABLE "django_evolution_renamebasemodel"("int_field" integer NOT NULL, "char_field" varchar(20) NOT NULL, "non-default_column_name" integer NOT NULL, "custom_db_col_name_indexed" integer NOT NULL, "fk_field_id" integer NOT NULL, "id" integer NOT NULL PRIMARY KEY);',
            'CREATE INDEX "django_evolution_renamebasemodel_custom_db_col_name_indexed" ON "django_evolution_renamebasemodel" ("custom_db_col_name_indexed");',
            'CREATE INDEX "django_evolution_renamebasemodel_fk_field_id" ON "django_evolution_renamebasemodel" ("fk_field_id");',
            'INSERT INTO "django_evolution_renamebasemodel" ("int_field", "char_field", "non-default_column_name", "custom_db_col_name_indexed", "fk_field_id", "id") SELECT "int_field", "char_field", "non-default_column_name", "custom_db_col_name_indexed", "fk_field_id", "id" FROM "TEMP_TABLE";',
            'DROP TABLE "TEMP_TABLE";',
        ]),
    'RenameNonDefaultColumnNameToNonDefaultNameAndTableModel': 
        '\n'.join([
            'CREATE TEMPORARY TABLE "TEMP_TABLE"("int_field" integer NOT NULL, "char_field" varchar(20) NOT NULL, "non-default_column_name2" integer NOT NULL, "custom_db_col_name_indexed" integer NOT NULL, "fk_field_id" integer NOT NULL, "id" integer NOT NULL PRIMARY KEY);',
            'INSERT INTO "TEMP_TABLE" SELECT "int_field", "char_field", "custom_db_col_name", "custom_db_col_name_indexed", "fk_field_id", "id" FROM "django_evolution_renamebasemodel";',
            'DROP TABLE "django_evolution_renamebasemodel";',
            'CREATE TABLE "django_evolution_renamebasemodel"("int_field" integer NOT NULL, "char_field" varchar(20) NOT NULL, "non-default_column_name2" integer NOT NULL, "custom_db_col_name_indexed" integer NOT NULL, "fk_field_id" integer NOT NULL, "id" integer NOT NULL PRIMARY KEY);',
            'CREATE INDEX "django_evolution_renamebasemodel_custom_db_col_name_indexed" ON "django_evolution_renamebasemodel" ("custom_db_col_name_indexed");',
            'CREATE INDEX "django_evolution_renamebasemodel_fk_field_id" ON "django_evolution_renamebasemodel" ("fk_field_id");',
            'INSERT INTO "django_evolution_renamebasemodel" ("int_field", "char_field", "non-default_column_name2", "custom_db_col_name_indexed", "fk_field_id", "id") SELECT "int_field", "char_field", "non-default_column_name2", "custom_db_col_name_indexed", "fk_field_id", "id" FROM "TEMP_TABLE";',
            'DROP TABLE "TEMP_TABLE";',
        ]),
    'RenameColumnCustomTableModel': 
        '\n'.join([
            'CREATE TEMPORARY TABLE "TEMP_TABLE"("id" integer NOT NULL PRIMARY KEY, "renamed_field" integer NOT NULL, "alt_value" varchar(20) NOT NULL);',
            'INSERT INTO "TEMP_TABLE" SELECT "id", "value", "alt_value" FROM "custom_rename_table_name";',
            'DROP TABLE "custom_rename_table_name";',
            'CREATE TABLE "custom_rename_table_name"("id" integer NOT NULL PRIMARY KEY, "renamed_field" integer NOT NULL, "alt_value" varchar(20) NOT NULL);',
            'INSERT INTO "custom_rename_table_name" ("id", "renamed_field", "alt_value") SELECT "id", "renamed_field", "alt_value" FROM "TEMP_TABLE";',
            'DROP TABLE "TEMP_TABLE";',
        ]),
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
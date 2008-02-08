add_field = {
    'AddNonNullNonCallableDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE `tests_testmodel` ADD COLUMN `added_field` integer ;',
            'UPDATE `tests_testmodel` SET `added_field` = 1 WHERE `added_field` IS NULL;',
            'ALTER TABLE `tests_testmodel` MODIFY COLUMN `added_field` integer NOT NULL;',
        ]),
    'AddNonNullCallableDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE `tests_testmodel` ADD COLUMN `added_field` integer ;',
            'UPDATE `tests_testmodel` SET `added_field` = `int_field` WHERE `added_field` IS NULL;',
            'ALTER TABLE `tests_testmodel` MODIFY COLUMN `added_field` integer NOT NULL;',
        ]),
    'AddNullColumnWithInitialDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE `tests_testmodel` ADD COLUMN `added_field` integer ;',
            'UPDATE `tests_testmodel` SET `added_field` = 1 WHERE `added_field` IS NULL;',
        ]),
    'AddStringDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE `tests_testmodel` ADD COLUMN `added_field` varchar(10) ;',
            'UPDATE `tests_testmodel` SET `added_field` = \'abc\\\'s xyz\' WHERE `added_field` IS NULL;',
            'ALTER TABLE `tests_testmodel` MODIFY COLUMN `added_field` varchar(10) NOT NULL;',
        ]),
    'AddDateDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE `tests_testmodel` ADD COLUMN `added_field` datetime ;',
            'UPDATE `tests_testmodel` SET `added_field` = 2007-12-13 16:42:00 WHERE `added_field` IS NULL;',
            'ALTER TABLE `tests_testmodel` MODIFY COLUMN `added_field` datetime NOT NULL;',
        ]),    
    'AddColumnWithDefaultDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE `tests_testmodel` ADD COLUMN `added_field` integer ;',
            'UPDATE `tests_testmodel` SET `added_field` = 42 WHERE `added_field` IS NULL;',
            'ALTER TABLE `tests_testmodel` MODIFY COLUMN `added_field` integer NOT NULL;',
        ]),
    'AddColumnWithEmptyStringDefaultDatabaseColumnModel':
        '\n'.join([
            'ALTER TABLE `tests_testmodel` ADD COLUMN `added_field` varchar(20) ;',
            'UPDATE `tests_testmodel` SET `added_field` = \'\' WHERE `added_field` IS NULL;',
            'ALTER TABLE `tests_testmodel` MODIFY COLUMN `added_field` varchar(20) NOT NULL;',
        ]),
    'NullDatabaseColumnModel': 
        'ALTER TABLE `tests_testmodel` ADD COLUMN `added_field` integer NULL ;',
    'NonDefaultDatabaseColumnModel': 
        'ALTER TABLE `tests_testmodel` ADD COLUMN `non-default_column` integer NULL ;',
    'AddDatabaseColumnCustomTableModel':  
        'ALTER TABLE `custom_table_name` ADD COLUMN `added_field` integer NULL ;',
    'AddIndexedDatabaseColumnModel': 
        '\n'.join([
            'ALTER TABLE `tests_testmodel` ADD COLUMN `add_field` integer NULL ;',
            'CREATE INDEX `tests_testmodel_add_field` ON `tests_testmodel` (`add_field`);'
        ]),
    'AddUniqueDatabaseColumnModel': 
        'ALTER TABLE `tests_testmodel` ADD COLUMN `added_field` integer NULL UNIQUE;',
    'ForeignKeyDatabaseColumnModel': 
        '\n'.join([
            'ALTER TABLE `tests_testmodel` ADD COLUMN `added_field_id` integer NULL REFERENCES `tests_addanchor1` (`id`) ;',
            'CREATE INDEX `tests_testmodel_added_field_id` ON `tests_testmodel` (`added_field_id`);'
        ]),
    'AddManyToManyDatabaseTableModel': 
        '\n'.join([
            'CREATE TABLE `tests_testmodel_added_field` (',
            '    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,',
            '    `testmodel_id` integer NOT NULL REFERENCES `tests_testmodel` (`id`),',
            '    `addanchor1_id` integer NOT NULL REFERENCES `tests_addanchor1` (`id`),',
            '    UNIQUE (`testmodel_id`, `addanchor1_id`)',
            ')',
            ';'
        ]),
     'AddManyToManyNonDefaultDatabaseTableModel': 
        '\n'.join([
            'CREATE TABLE `tests_testmodel_added_field` (',
            '    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,',
            '    `testmodel_id` integer NOT NULL REFERENCES `tests_testmodel` (`id`),',
            '    `addanchor2_id` integer NOT NULL REFERENCES `custom_add_anchor_table` (`id`),',
            '    UNIQUE (`testmodel_id`, `addanchor2_id`)',
            ')',
            ';'
        ]),
     'ManyToManySelf': 
        '\n'.join([
            'CREATE TABLE `tests_testmodel_added_field` (',
            '    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,',
            '    `from_testmodel_id` integer NOT NULL REFERENCES `tests_testmodel` (`id`),',
            '    `to_testmodel_id` integer NOT NULL REFERENCES `tests_testmodel` (`id`),',
            '    UNIQUE (`from_testmodel_id`, `to_testmodel_id`)',
            ')',
            ';'
        ]),
}

delete_field = {
    'DefaultNamedColumnModel': 
        'ALTER TABLE `tests_testmodel` DROP COLUMN `int_field` CASCADE;',
    'NonDefaultNamedColumnModel': 
        'ALTER TABLE `tests_testmodel` DROP COLUMN `non-default_db_column` CASCADE;',
    'ConstrainedColumnModel': 
        'ALTER TABLE `tests_testmodel` DROP COLUMN `int_field3` CASCADE;',
    'DefaultManyToManyModel': 
        'DROP TABLE `tests_testmodel_m2m_field1`;',
    'NonDefaultManyToManyModel': 
        'DROP TABLE `non-default_m2m_table`;',
    'DeleteForeignKeyModel': 
        'ALTER TABLE `tests_testmodel` DROP COLUMN `fk_field1_id` CASCADE;',
    'DeleteColumnCustomTableModel': 
        'ALTER TABLE `custom_table_name` DROP COLUMN `value` CASCADE;',
}

delete_model = {
    'BasicModel': 
        'DROP TABLE `tests_basicmodel`;',
    'BasicWithM2MModel': 
        '\n'.join([
            'DROP TABLE `tests_basicwithm2mmodel_m2m`;',
            'DROP TABLE `tests_basicwithm2mmodel`;'
        ]),
    'CustomTableModel': 
        'DROP TABLE `custom_table_name`;',
    'CustomTableWithM2MModel': 
        '\n'.join([
            'DROP TABLE `another_custom_table_name_m2m`;',
            'DROP TABLE `another_custom_table_name`;'
        ]),
}

delete_application = {
    'DeleteApplication':
        '\n'.join([
            'DROP TABLE `tests_appdeleteanchor1`;',
            'DROP TABLE `tests_testmodel_anchor_m2m`;',
            'DROP TABLE `tests_testmodel`;',
            'DROP TABLE `app_delete_custom_add_anchor_table`;',
            'DROP TABLE `app_delete_custom_table_name`;',
        ]),
}

rename_field = {
    'RenameColumnModel': 
        'ALTER TABLE `tests_testmodel` CHANGE `int_field` `renamed_field` integer NOT NULL;',
    'RenameColumnWithTableNameModel': 
        'ALTER TABLE `tests_testmodel` CHANGE `int_field` `renamed_field` integer NOT NULL;',
    'RenamePrimaryKeyColumnModel': 
        'ALTER TABLE `tests_testmodel` CHANGE `id` `my_pk_id`;',
    'RenameForeignKeyColumnModel': 
        'ALTER TABLE `tests_testmodel` CHANGE `fk_field_id` `renamed_field_id` integer NOT NULL;',
    'RenameNonDefaultColumnNameModel': 
        'ALTER TABLE `tests_testmodel` CHANGE `custom_db_col_name` `renamed_field` integer NOT NULL;',
    'RenameNonDefaultColumnNameToNonDefaultNameModel': 
        'ALTER TABLE `tests_testmodel` CHANGE `custom_db_col_name` `non-default_column_name` integer NOT NULL;',
    'RenameNonDefaultColumnNameToNonDefaultNameAndTableModel': 
        'ALTER TABLE `tests_testmodel` CHANGE `custom_db_col_name` `non-default_column_name2` integer NOT NULL;',
    'RenameColumnCustomTableModel': 
        'ALTER TABLE `custom_rename_table_name` CHANGE `value` `renamed_field` integer NOT NULL;',
    'RenameManyToManyTableModel': 
        'ALTER TABLE `tests_testmodel_m2m_field` RENAME TO `tests_testmodel_renamed_field`;',
    'RenameManyToManyTableWithColumnNameModel': 
        'ALTER TABLE `tests_testmodel_m2m_field` RENAME TO `tests_testmodel_renamed_field`;',
    'RenameNonDefaultManyToManyTableModel': 
        'ALTER TABLE `non-default_db_table` RENAME TO `tests_testmodel_renamed_field`;',
}


sql_mutation = {
    'SQLMutationSequence': """[
...    SQLMutation('first-two-fields', [
...        'ALTER TABLE `tests_testmodel` ADD COLUMN `added_field1` integer NULL;',
...        'ALTER TABLE `tests_testmodel` ADD COLUMN `added_field2` integer NULL;'
...    ], update_first_two),
...    SQLMutation('third-field', [
...        'ALTER TABLE `tests_testmodel` ADD COLUMN `added_field3` integer NULL;',
...    ], update_third)]
""",
    'SQLMutationOutput': 
        '\n'.join([
            'ALTER TABLE `tests_testmodel` ADD COLUMN `added_field1` integer NULL;',
            'ALTER TABLE `tests_testmodel` ADD COLUMN `added_field2` integer NULL;',
            'ALTER TABLE `tests_testmodel` ADD COLUMN `added_field3` integer NULL;',
        ]),
}

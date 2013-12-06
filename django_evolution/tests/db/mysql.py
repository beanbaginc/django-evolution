from django_evolution.tests.utils import (generate_constraint_name,
                                          generate_index_name)


add_field = {
    'AddNonNullNonCallableColumnModel': '\n'.join([
        'ALTER TABLE `tests_testmodel`'
        ' ADD COLUMN `added_field` integer  DEFAULT 1;',

        'ALTER TABLE `tests_testmodel`'
        ' ALTER COLUMN `added_field` DROP DEFAULT;',

        'ALTER TABLE `tests_testmodel`'
        ' MODIFY COLUMN `added_field` integer NOT NULL;',
    ]),

    'AddNonNullCallableColumnModel': '\n'.join([
        'ALTER TABLE `tests_testmodel` ADD COLUMN `added_field` integer ;',

        'UPDATE `tests_testmodel`'
        ' SET `added_field` = `int_field` WHERE `added_field` IS NULL;',

        'ALTER TABLE `tests_testmodel`'
        ' MODIFY COLUMN `added_field` integer NOT NULL;',
    ]),

    'AddNullColumnWithInitialColumnModel': '\n'.join([
        'ALTER TABLE `tests_testmodel`'
        ' ADD COLUMN `added_field` integer  DEFAULT 1;',

        'ALTER TABLE `tests_testmodel`'
        ' ALTER COLUMN `added_field` DROP DEFAULT;',
    ]),

    'AddStringColumnModel': '\n'.join([
        'ALTER TABLE `tests_testmodel`'
        ' ADD COLUMN `added_field` varchar(10)'
        '  DEFAULT \'abc\\\'s xyz\';',

        'ALTER TABLE `tests_testmodel`'
        ' ALTER COLUMN `added_field` DROP DEFAULT;',

        'ALTER TABLE `tests_testmodel`'
        ' MODIFY COLUMN `added_field` varchar(10) NOT NULL;',
    ]),

    'AddDateColumnModel': '\n'.join([
        'ALTER TABLE `tests_testmodel`'
        ' ADD COLUMN `added_field` datetime'
        '  DEFAULT 2007-12-13 16:42:00;',

        'ALTER TABLE `tests_testmodel`'
        ' ALTER COLUMN `added_field` DROP DEFAULT;',

        'ALTER TABLE `tests_testmodel`'
        ' MODIFY COLUMN `added_field` datetime NOT NULL;',
    ]),

    'AddDefaultColumnModel': '\n'.join([
        'ALTER TABLE `tests_testmodel`'
        ' ADD COLUMN `added_field` integer  DEFAULT 42;',

        'ALTER TABLE `tests_testmodel`'
        ' ALTER COLUMN `added_field` DROP DEFAULT;',

        'ALTER TABLE `tests_testmodel`'
        ' MODIFY COLUMN `added_field` integer NOT NULL;',
    ]),

    'AddMismatchInitialBoolColumnModel': '\n'.join([
        'ALTER TABLE `tests_testmodel`'
        ' ADD COLUMN `added_field` bool  DEFAULT 0;',

        'ALTER TABLE `tests_testmodel`'
        ' ALTER COLUMN `added_field` DROP DEFAULT;',

        'ALTER TABLE `tests_testmodel`'
        ' MODIFY COLUMN `added_field` bool NOT NULL;',
    ]),

    'AddEmptyStringDefaultColumnModel': '\n'.join([
        'ALTER TABLE `tests_testmodel`'
        ' ADD COLUMN `added_field` varchar(20)  DEFAULT \'\';',

        'ALTER TABLE `tests_testmodel`'
        ' ALTER COLUMN `added_field` DROP DEFAULT;',

        'ALTER TABLE `tests_testmodel`'
        ' MODIFY COLUMN `added_field` varchar(20) NOT NULL;',
    ]),

    'AddNullColumnModel': (
        'ALTER TABLE `tests_testmodel`'
        ' ADD COLUMN `added_field` integer NULL ;'
    ),

    'NonDefaultColumnModel': (
        'ALTER TABLE `tests_testmodel`'
        ' ADD COLUMN `non-default_column` integer NULL ;'
    ),

    'AddColumnCustomTableModel': (
        'ALTER TABLE `custom_table_name`'
        ' ADD COLUMN `added_field` integer NULL ;'
    ),

    'AddIndexedColumnModel': '\n'.join([
        'ALTER TABLE `tests_testmodel` ADD COLUMN `add_field` integer NULL ;',

        'CREATE INDEX `%s` ON `tests_testmodel` (`add_field`);'
        % generate_index_name('tests_testmodel', 'add_field')
    ]),

    'AddUniqueColumnModel': (
        'ALTER TABLE `tests_testmodel`'
        ' ADD COLUMN `added_field` integer NULL UNIQUE;'
    ),

    'AddUniqueIndexedModel': (
        'ALTER TABLE `tests_testmodel`'
        ' ADD COLUMN `added_field` integer NULL UNIQUE;'
    ),

    'AddForeignKeyModel': '\n'.join([
        'ALTER TABLE `tests_testmodel`'
        ' ADD COLUMN `added_field_id` integer NULL'
        ' REFERENCES `tests_addanchor1` (`id`) ;',

        'CREATE INDEX `%s` ON `tests_testmodel` (`added_field_id`);'
        % generate_index_name('tests_testmodel', 'added_field_id',
                              'added_field'),
    ]),

    'AddManyToManyDatabaseTableModel': '\n'.join([
        'CREATE TABLE `tests_testmodel_added_field` (',
        '    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,',
        '    `testmodel_id` integer NOT NULL,',
        '    `addanchor1_id` integer NOT NULL,',
        '    UNIQUE (`testmodel_id`, `addanchor1_id`)',
        ')',
        ';',

        'ALTER TABLE `tests_testmodel_added_field`'
        ' ADD CONSTRAINT `%s` FOREIGN KEY (`addanchor1_id`)'
        ' REFERENCES `tests_addanchor1` (`id`);'
        % generate_constraint_name('addanchor1_id', 'id',
                                   'tests_testmodel_added_field',
                                   'tests_addanchor1'),

        'ALTER TABLE `tests_testmodel_added_field`'
        ' ADD CONSTRAINT `%s` FOREIGN KEY (`testmodel_id`)'
        ' REFERENCES `tests_testmodel` (`id`);'
        % generate_constraint_name('testmodel_id', 'id',
                                   'tests_testmodel_added_field',
                                   'tests_testmodel'),
    ]),

    'AddManyToManyNonDefaultDatabaseTableModel': '\n'.join([
        'CREATE TABLE `tests_testmodel_added_field` (',
        '    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,',
        '    `testmodel_id` integer NOT NULL,',
        '    `addanchor2_id` integer NOT NULL,',
        '    UNIQUE (`testmodel_id`, `addanchor2_id`)',
        ')',
        ';',

        'ALTER TABLE `tests_testmodel_added_field`'
        ' ADD CONSTRAINT `%s` FOREIGN KEY (`addanchor2_id`)'
        ' REFERENCES `custom_add_anchor_table` (`id`);'
        % generate_constraint_name('addanchor2_id', 'id',
                                   'tests_testmodel_added_field',
                                   'custom_add_anchor_table'),

        'ALTER TABLE `tests_testmodel_added_field`'
        ' ADD CONSTRAINT `%s` FOREIGN KEY (`testmodel_id`)'
        ' REFERENCES `tests_testmodel` (`id`);'
        % generate_constraint_name('testmodel_id', 'id',
                                   'tests_testmodel_added_field',
                                   'tests_testmodel'),
    ]),

    'AddManyToManySelf': '\n'.join([
        'CREATE TABLE `tests_testmodel_added_field` (',
        '    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,',
        '    `from_testmodel_id` integer NOT NULL,',
        '    `to_testmodel_id` integer NOT NULL,',
        '    UNIQUE (`from_testmodel_id`, `to_testmodel_id`)',
        ')',
        ';',

        'ALTER TABLE `tests_testmodel_added_field`'
        ' ADD CONSTRAINT `%s` FOREIGN KEY (`from_testmodel_id`)'
        ' REFERENCES `tests_testmodel` (`id`);'
        % generate_constraint_name('from_testmodel_id', 'id',
                                   'tests_testmodel_added_field',
                                   'tests_testmodel'),

        'ALTER TABLE `tests_testmodel_added_field`'
        ' ADD CONSTRAINT `%s` FOREIGN KEY (`to_testmodel_id`)'
        ' REFERENCES `tests_testmodel` (`id`);'
        % generate_constraint_name('to_testmodel_id', 'id',
                                   'tests_testmodel_added_field',
                                   'tests_testmodel'),
    ]),
}

delete_field = {
    'DefaultNamedColumnModel': (
        'ALTER TABLE `tests_testmodel` DROP COLUMN `int_field` CASCADE;'
    ),

    'NonDefaultNamedColumnModel': (
        'ALTER TABLE `tests_testmodel`'
        ' DROP COLUMN `non-default_db_column` CASCADE;'
    ),

    'ConstrainedColumnModel': (
        'ALTER TABLE `tests_testmodel` DROP COLUMN `int_field3` CASCADE;'
    ),

    'DefaultManyToManyModel': (
        'DROP TABLE `tests_testmodel_m2m_field1`;'
    ),

    'NonDefaultManyToManyModel': (
        'DROP TABLE `non-default_m2m_table`;'
    ),

    'DeleteForeignKeyModel': '\n'.join([
        'ALTER TABLE `tests_testmodel` DROP FOREIGN KEY `%s`;'
        % generate_constraint_name('fk_field1_id', 'id',
                                   'tests_testmodel',
                                   'tests_deleteanchor1'),

        'ALTER TABLE `tests_testmodel` DROP COLUMN `fk_field1_id` CASCADE;',
    ]),

    'DeleteColumnCustomTableModel': (
        'ALTER TABLE `custom_table_name` DROP COLUMN `value` CASCADE;'
    ),
}

change_field = {
    'SetNotNullChangeModelWithConstant': '\n'.join([
        'UPDATE `tests_testmodel`'
        ' SET `char_field1` = \'abc\\\'s xyz\' WHERE `char_field1` IS NULL;',

        'ALTER TABLE `tests_testmodel`'
        ' MODIFY COLUMN `char_field1` varchar(25) NOT NULL;',
    ]),

    'SetNotNullChangeModelWithCallable': '\n'.join([
        'UPDATE `tests_testmodel`'
        ' SET `char_field1` = `char_field` WHERE `char_field1` IS NULL;',

        'ALTER TABLE `tests_testmodel`'
        ' MODIFY COLUMN `char_field1` varchar(25) NOT NULL;',
    ]),

    'SetNullChangeModel': (
        'ALTER TABLE `tests_testmodel`'
        ' MODIFY COLUMN `char_field2` varchar(30) DEFAULT NULL;'
    ),

    'NoOpChangeModel': '',

    'IncreasingMaxLengthChangeModel': '\n'.join([
        'UPDATE `tests_testmodel` SET `char_field`=LEFT(`char_field`,45);',

        'ALTER TABLE `tests_testmodel`'
        ' MODIFY COLUMN `char_field` varchar(45);',
    ]),

    'DecreasingMaxLengthChangeModel': '\n'.join([
        'UPDATE `tests_testmodel` SET `char_field`=LEFT(`char_field`,1);',

        'ALTER TABLE `tests_testmodel` MODIFY COLUMN `char_field` varchar(1);',
    ]),

    'DBColumnChangeModel': (
        'ALTER TABLE `tests_testmodel`'
        ' CHANGE COLUMN `custom_db_column` `customised_db_column`'
        ' integer NOT NULL;'
    ),

    'M2MDBTableChangeModel': '\n'.join([
        'ALTER TABLE `change_field_non-default_m2m_table`'
        ' DROP FOREIGN KEY `%s`;'
        % generate_constraint_name('testmodel_id', 'my_id',
                                   'change_field_non-default_m2m_table',
                                   'tests_testmodel'),

        'RENAME TABLE `change_field_non-default_m2m_table`'
        ' TO `custom_m2m_db_table_name`;',

        'ALTER TABLE `custom_m2m_db_table_name`'
        ' ADD CONSTRAINT `%s` FOREIGN KEY (`testmodel_id`)'
        ' REFERENCES `tests_testmodel` (`my_id`);'
        % generate_constraint_name('testmodel_id', 'my_id',
                                   'custom_m2m_db_table_name',
                                   'tests_testmodel'),
    ]),

    'AddDBIndexChangeModel': (
        'CREATE INDEX `%s` ON `tests_testmodel` (`int_field2`);'
        % generate_index_name('tests_testmodel', 'int_field2')
    ),

    'RemoveDBIndexChangeModel': (
        'DROP INDEX `%s` ON `tests_testmodel`;'
        % generate_index_name('tests_testmodel', 'int_field1')
    ),

    'AddUniqueChangeModel': (
        'CREATE UNIQUE INDEX int_field4 ON `tests_testmodel`(`int_field4`);'
    ),

    'RemoveUniqueChangeModel': (
        'DROP INDEX int_field3 ON `tests_testmodel`;'
    ),

    'MultiAttrChangeModel': '\n'.join([
        'ALTER TABLE `tests_testmodel`'
        ' MODIFY COLUMN `char_field2` varchar(30) DEFAULT NULL;',

        'ALTER TABLE `tests_testmodel`'
        ' CHANGE COLUMN `custom_db_column` `custom_db_column2`'
        ' integer NOT NULL;',

        'UPDATE `tests_testmodel` SET `char_field`=LEFT(`char_field`,35);',

        'ALTER TABLE `tests_testmodel`'
        ' MODIFY COLUMN `char_field` varchar(35);',
    ]),

    'MultiAttrSingleFieldChangeModel': '\n'.join([
        'UPDATE `tests_testmodel` SET `char_field2`=LEFT(`char_field2`,35);',

        'ALTER TABLE `tests_testmodel`'
        ' MODIFY COLUMN `char_field2` varchar(35);',

        'ALTER TABLE `tests_testmodel`'
        ' MODIFY COLUMN `char_field2` varchar(35) DEFAULT NULL;',
    ]),

    'RedundantAttrsChangeModel': '\n'.join([
        'ALTER TABLE `tests_testmodel`'
        ' MODIFY COLUMN `char_field2` varchar(30) DEFAULT NULL;',

        'ALTER TABLE `tests_testmodel`'
        ' CHANGE COLUMN `custom_db_column` `custom_db_column3`'
        ' integer NOT NULL;',

        'UPDATE `tests_testmodel` SET `char_field`=LEFT(`char_field`,35);',

        'ALTER TABLE `tests_testmodel`'
        ' MODIFY COLUMN `char_field` varchar(35);',
    ]),
}

delete_model = {
    'BasicModel': (
        'DROP TABLE `tests_basicmodel`;'
    ),

    'BasicWithM2MModel': '\n'.join([
        'DROP TABLE `tests_basicwithm2mmodel_m2m`;',
        'DROP TABLE `tests_basicwithm2mmodel`;'
    ]),

    'CustomTableModel': (
        'DROP TABLE `custom_table_name`;'
    ),

    'CustomTableWithM2MModel': '\n'.join([
        'DROP TABLE `another_custom_table_name_m2m`;',
        'DROP TABLE `another_custom_table_name`;'
    ]),
}

delete_application = {
    'DeleteApplication': '\n'.join([
        'DROP TABLE `tests_appdeleteanchor1`;',
        'DROP TABLE `app_delete_custom_add_anchor_table`;',
        'DROP TABLE `tests_testmodel_anchor_m2m`;',
        'DROP TABLE `tests_testmodel`;',
        'DROP TABLE `app_delete_custom_table_name`;',
    ]),

    'DeleteApplicationWithoutDatabase': "",
}

rename_field = {
    'RenameColumnModel': (
        'ALTER TABLE `tests_testmodel`'
        ' CHANGE COLUMN `int_field` `renamed_field` integer NOT NULL;'
    ),

    'RenameColumnWithTableNameModel': (
        'ALTER TABLE `tests_testmodel`'
        ' CHANGE COLUMN `int_field` `renamed_field` integer NOT NULL;'
    ),

    'RenamePrimaryKeyColumnModel': '\n'.join([
        'ALTER TABLE `non-default_db_table` DROP FOREIGN KEY `%s`;'
        % generate_constraint_name('testmodel_id', 'id',
                                   'non-default_db_table',
                                   'tests_testmodel'),

        'ALTER TABLE `tests_testmodel_m2m_field` DROP FOREIGN KEY `%s`;'
        % generate_constraint_name('testmodel_id', 'id',
                                   'tests_testmodel_m2m_field',
                                   'tests_testmodel'),

        'ALTER TABLE `tests_testmodel`'
        ' DROP PRIMARY KEY, CHANGE COLUMN `id` `my_pk_id`'
        ' integer AUTO_INCREMENT NOT NULL PRIMARY KEY UNIQUE;',

        'ALTER TABLE `non-default_db_table`'
        ' ADD CONSTRAINT `%s` FOREIGN KEY (`testmodel_id`)'
        ' REFERENCES `tests_testmodel` (`my_pk_id`);'
        % generate_constraint_name('testmodel_id', 'my_pk_id',
                                   'non-default_db_table',
                                   'tests_testmodel'),

        'ALTER TABLE `tests_testmodel_m2m_field`'
        ' ADD CONSTRAINT `%s` FOREIGN KEY (`testmodel_id`)'
        ' REFERENCES `tests_testmodel` (`my_pk_id`);'
        % generate_constraint_name('testmodel_id', 'my_pk_id',
                                   'tests_testmodel_m2m_field',
                                   'tests_testmodel'),
    ]),

    'RenameForeignKeyColumnModel': (
        'ALTER TABLE `tests_testmodel`'
        ' CHANGE COLUMN `fk_field_id` `renamed_field_id` integer NOT NULL;'
    ),

    'RenameNonDefaultColumnNameModel': (
        'ALTER TABLE `tests_testmodel`'
        ' CHANGE COLUMN `custom_db_col_name` `renamed_field`'
        ' integer NOT NULL;'
    ),

    'RenameNonDefaultColumnNameToNonDefaultNameModel': (
        'ALTER TABLE `tests_testmodel`'
        ' CHANGE COLUMN `custom_db_col_name` `non-default_column_name`'
        ' integer NOT NULL;'
    ),

    'RenameNonDefaultColumnNameToNonDefaultNameAndTableModel': (
        'ALTER TABLE `tests_testmodel`'
        ' CHANGE COLUMN `custom_db_col_name` `non-default_column_name2`'
        ' integer NOT NULL;'
    ),

    'RenameColumnCustomTableModel': (
        'ALTER TABLE `custom_rename_table_name`'
        ' CHANGE COLUMN `value` `renamed_field` integer NOT NULL;'
    ),

    'RenameManyToManyTableModel': '\n'.join([
        'ALTER TABLE `tests_testmodel_m2m_field` DROP FOREIGN KEY `%s`;'
        % generate_constraint_name('testmodel_id', 'id',
                                   'tests_testmodel_m2m_field',
                                   'tests_testmodel'),

        'RENAME TABLE `tests_testmodel_m2m_field`'
        ' TO `tests_testmodel_renamed_field`;',

        'ALTER TABLE `tests_testmodel_renamed_field`'
        ' ADD CONSTRAINT `%s` FOREIGN KEY (`testmodel_id`)'
        ' REFERENCES `tests_testmodel` (`id`);'
        % generate_constraint_name('testmodel_id', 'id',
                                   'tests_testmodel_renamed_field',
                                   'tests_testmodel'),
    ]),

    'RenameManyToManyTableWithColumnNameModel': '\n'.join([
        'ALTER TABLE `tests_testmodel_m2m_field` DROP FOREIGN KEY `%s`;'
        % generate_constraint_name('testmodel_id', 'id',
                                   'tests_testmodel_m2m_field',
                                   'tests_testmodel'),

        'RENAME TABLE `tests_testmodel_m2m_field`'
        ' TO `tests_testmodel_renamed_field`;',

        'ALTER TABLE `tests_testmodel_renamed_field`'
        ' ADD CONSTRAINT `%s` FOREIGN KEY (`testmodel_id`)'
        ' REFERENCES `tests_testmodel` (`id`);'
        % generate_constraint_name('testmodel_id', 'id',
                                   'tests_testmodel_renamed_field',
                                   'tests_testmodel'),
    ]),

    'RenameNonDefaultManyToManyTableModel': (
        'RENAME TABLE `non-default_db_table`'
        ' TO `tests_testmodel_renamed_field`;'
    ),
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
    'SQLMutationOutput': '\n'.join([
        'ALTER TABLE `tests_testmodel`'
        ' ADD COLUMN `added_field1` integer NULL;',

        'ALTER TABLE `tests_testmodel`'
        ' ADD COLUMN `added_field2` integer NULL;',

        'ALTER TABLE `tests_testmodel`'
        ' ADD COLUMN `added_field3` integer NULL;',
    ]),
}

generics = {
    'DeleteColumnModel': (
        'ALTER TABLE `tests_testmodel` DROP COLUMN `char_field` CASCADE;'
    ),
}

inheritance = {
    'AddToChildModel': '\n'.join([
        'ALTER TABLE `tests_childmodel`'
        ' ADD COLUMN `added_field` integer  DEFAULT 42;',

        'ALTER TABLE `tests_childmodel`'
        ' ALTER COLUMN `added_field` DROP DEFAULT;',

        'ALTER TABLE `tests_childmodel`'
        ' MODIFY COLUMN `added_field` integer NOT NULL;',
    ]),

    'DeleteFromChildModel': (
        'ALTER TABLE `tests_childmodel` DROP COLUMN `int_field` CASCADE;'
    ),
}

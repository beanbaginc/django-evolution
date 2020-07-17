from __future__ import unicode_literals

import django

from django_evolution.tests.utils import (make_generate_index_name,
                                          make_generate_unique_constraint_name,
                                          test_connections)


connection = test_connections['sqlite3']
generate_index_name = make_generate_index_name(connection)
generate_unique_constraint_name = \
    make_generate_unique_constraint_name(connection)


try:
    # Django >= 1.8
    data_types_suffix = connection.data_types_suffix
except AttributeError:
    try:
        # Django == 1.7
        data_types_suffix = connection.creation.data_types_suffix
    except AttributeError:
        # Django < 1.7
        data_types_suffix = {}


def get_field_suffix(field_type):
    try:
        return ' %s' % data_types_suffix[field_type]
    except KeyError:
        return ''


add_field = {
    'AddNonNullNonCallableColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "added_field" integer NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("id", "char_field", "int_field")'
        ' SELECT "id", "char_field", "int_field"'
        ' FROM "tests_testmodel";',

        'UPDATE "TEMP_TABLE" SET "added_field" = 1;',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'AddNonNullCallableColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "added_field" integer NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("id", "char_field", "int_field")'
        ' SELECT "id", "char_field", "int_field"'
        ' FROM "tests_testmodel";',

        'UPDATE "TEMP_TABLE" SET "added_field" = "int_field";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'AddNullColumnWithInitialColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "added_field" integer NULL);',

        'INSERT INTO "TEMP_TABLE" ("id", "char_field", "int_field")'
        ' SELECT "id", "char_field", "int_field"'
        ' FROM "tests_testmodel";',

        'UPDATE "TEMP_TABLE" SET "added_field" = 1;',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'AddStringColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "added_field" varchar(10) NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("id", "char_field", "int_field")'
        ' SELECT "id", "char_field", "int_field"'
        ' FROM "tests_testmodel";',

        'UPDATE "TEMP_TABLE" SET "added_field" = \'abc\\\'s xyz\';',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'AddBlankStringColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "added_field" varchar(10) NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("id", "char_field", "int_field")'
        ' SELECT "id", "char_field", "int_field"'
        ' FROM "tests_testmodel";',

        'UPDATE "TEMP_TABLE" SET "added_field" = \'\';',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'AddDateColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "added_field" datetime NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("id", "char_field", "int_field")'
        ' SELECT "id", "char_field", "int_field"'
        ' FROM "tests_testmodel";',

        'UPDATE "TEMP_TABLE" SET "added_field" = 2007-12-13 16:42:00;',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'AddDefaultColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "added_field" integer NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("id", "char_field", "int_field")'
        ' SELECT "id", "char_field", "int_field"'
        ' FROM "tests_testmodel";',

        'UPDATE "TEMP_TABLE" SET "added_field" = 42;',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'AddMismatchInitialBoolColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "added_field" bool NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("id", "char_field", "int_field")'
        ' SELECT "id", "char_field", "int_field"'
        ' FROM "tests_testmodel";',

        'UPDATE "TEMP_TABLE" SET "added_field" = 0;',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'AddEmptyStringDefaultColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "added_field" varchar(20) NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("id", "char_field", "int_field")'
        ' SELECT "id", "char_field", "int_field"'
        ' FROM "tests_testmodel";',

        'UPDATE "TEMP_TABLE" SET "added_field" = \'\';',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'AddNullColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("int_field" integer NOT NULL,'
        ' "id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "added_field" integer NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("int_field", "id", "char_field")'
        ' SELECT "int_field", "id", "char_field"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'NonDefaultColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "non-default_column" integer NULL);',

        'INSERT INTO "TEMP_TABLE" ("id", "char_field", "int_field")'
        ' SELECT "id", "char_field", "int_field"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'AddColumnCustomTableModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "value" integer NOT NULL,'
        ' "alt_value" varchar(20) NOT NULL,'
        ' "added_field" integer NULL);',

        'INSERT INTO "TEMP_TABLE" ("id", "value", "alt_value")'
        ' SELECT "id", "value", "alt_value"'
        ' FROM "custom_table_name";',

        'DROP TABLE "custom_table_name";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "custom_table_name";',
    ],

    'AddIndexedColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "add_field" integer NULL);',

        'INSERT INTO "TEMP_TABLE" ("id", "char_field", "int_field")'
        ' SELECT "id", "char_field", "int_field"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" ("add_field");'
        % generate_index_name('tests_testmodel', 'add_field',
                              'add_field'),
    ],

    'AddUniqueColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "added_field" integer NULL UNIQUE);',

        'INSERT INTO "TEMP_TABLE" ("id", "char_field", "int_field")'
        ' SELECT "id", "char_field", "int_field"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'AddUniqueIndexedModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "added_field" integer NULL UNIQUE);',

        'INSERT INTO "TEMP_TABLE" ("id", "char_field", "int_field")'
        ' SELECT "id", "char_field", "int_field"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'AddForeignKeyModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "added_field_id" integer NULL REFERENCES "tests_addanchor1" ("id")'
        ' DEFERRABLE INITIALLY DEFERRED);',

        'INSERT INTO "TEMP_TABLE" ("id", "char_field", "int_field")'
        ' SELECT "id", "char_field", "int_field"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" ("added_field_id");'
        % generate_index_name('tests_testmodel', 'added_field_id',
                              'added_field'),
    ],
}

if django.VERSION[:2] >= (2, 0):
    add_field.update({
        'AddManyToManyDatabaseTableModel': [
            'CREATE TABLE "tests_testmodel_added_field" '
            '("id" integer NOT NULL PRIMARY KEY%s,'
            ' "testmodel_id" integer NOT NULL'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED,'
            ' "addanchor1_id" integer NOT NULL'
            ' REFERENCES "tests_addanchor1" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED'
            ');'
            % get_field_suffix('AutoField'),

            'CREATE UNIQUE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("testmodel_id", "addanchor1_id");'
            % generate_unique_constraint_name(
                'tests_testmodel_added_field',
                ['testmodel_id', 'addanchor1_id']),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'testmodel_id'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("addanchor1_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'addanchor1_id'),
        ],

        'AddManyToManyNonDefaultDatabaseTableModel': [
            'CREATE TABLE "tests_testmodel_added_field" '
            '("id" integer NOT NULL PRIMARY KEY%s,'
            ' "testmodel_id" integer NOT NULL'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED,'
            ' "addanchor2_id" integer NOT NULL'
            ' REFERENCES "custom_add_anchor_table" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED'
            ');'
            % get_field_suffix('AutoField'),

            'CREATE UNIQUE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("testmodel_id", "addanchor2_id");'
            % generate_unique_constraint_name(
                'tests_testmodel_added_field',
                ['testmodel_id', 'addanchor2_id']),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'testmodel_id'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("addanchor2_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'addanchor2_id'),
        ],

        'AddManyToManySelf': [
            'CREATE TABLE "tests_testmodel_added_field" '
            '("id" integer NOT NULL PRIMARY KEY%s,'
            ' "from_testmodel_id" integer NOT NULL'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED,'
            ' "to_testmodel_id" integer NOT NULL'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED'
            ');'
            % get_field_suffix('AutoField'),

            'CREATE UNIQUE INDEX "%s" ON "tests_testmodel_added_field"'
            ' ("from_testmodel_id", "to_testmodel_id");'
            % generate_unique_constraint_name(
                'tests_testmodel_added_field',
                ['from_testmodel_id', 'to_testmodel_id']),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("from_testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'from_testmodel_id'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("to_testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'to_testmodel_id'),
        ],
    })
elif django.VERSION[:2] >= (1, 9):
    add_field.update({
        'AddManyToManyDatabaseTableModel': [
            'CREATE TABLE "tests_testmodel_added_field" '
            '("id" integer NOT NULL PRIMARY KEY%s,'
            ' "testmodel_id" integer NOT NULL'
            ' REFERENCES "tests_testmodel" ("id"),'
            ' "addanchor1_id" integer NOT NULL'
            ' REFERENCES "tests_addanchor1" ("id")'
            ');'
            % get_field_suffix('AutoField'),

            'CREATE UNIQUE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("testmodel_id", "addanchor1_id");'
            % generate_unique_constraint_name(
                'tests_testmodel_added_field',
                ['testmodel_id', 'addanchor1_id']),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'testmodel_id'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("addanchor1_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'addanchor1_id'),
        ],

        'AddManyToManyNonDefaultDatabaseTableModel': [
            'CREATE TABLE "tests_testmodel_added_field" '
            '("id" integer NOT NULL PRIMARY KEY%s,'
            ' "testmodel_id" integer NOT NULL'
            ' REFERENCES "tests_testmodel" ("id"),'
            ' "addanchor2_id" integer NOT NULL'
            ' REFERENCES "custom_add_anchor_table" ("id")'
            ');'
            % get_field_suffix('AutoField'),

            'CREATE UNIQUE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("testmodel_id", "addanchor2_id");'
            % generate_unique_constraint_name(
                'tests_testmodel_added_field',
                ['testmodel_id', 'addanchor2_id']),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'testmodel_id'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("addanchor2_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'addanchor2_id'),
        ],

        'AddManyToManySelf': [
            'CREATE TABLE "tests_testmodel_added_field" '
            '("id" integer NOT NULL PRIMARY KEY%s,'
            ' "from_testmodel_id" integer NOT NULL'
            ' REFERENCES "tests_testmodel" ("id"),'
            ' "to_testmodel_id" integer NOT NULL'
            ' REFERENCES "tests_testmodel" ("id")'
            ');'
            % get_field_suffix('AutoField'),

            'CREATE UNIQUE INDEX "%s" ON "tests_testmodel_added_field"'
            ' ("from_testmodel_id", "to_testmodel_id");'
            % generate_unique_constraint_name(
                'tests_testmodel_added_field',
                ['from_testmodel_id', 'to_testmodel_id']),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("from_testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'from_testmodel_id'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("to_testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'to_testmodel_id'),
        ],
    })
elif django.VERSION[:2] >= (1, 7):
    add_field.update({
        'AddManyToManyDatabaseTableModel': [
            'CREATE TABLE "tests_testmodel_added_field" '
            '("id" integer NOT NULL PRIMARY KEY%s,'
            ' "testmodel_id" integer NOT NULL'
            ' REFERENCES "tests_testmodel" ("id"),'
            ' "addanchor1_id" integer NOT NULL'
            ' REFERENCES "tests_addanchor1" ("id"),'
            ' UNIQUE ("testmodel_id", "addanchor1_id")'
            ');'
            % get_field_suffix('AutoField'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'testmodel_id'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("addanchor1_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'addanchor1_id'),
        ],

        'AddManyToManyNonDefaultDatabaseTableModel': [
            'CREATE TABLE "tests_testmodel_added_field" '
            '("id" integer NOT NULL PRIMARY KEY%s,'
            ' "testmodel_id" integer NOT NULL'
            ' REFERENCES "tests_testmodel" ("id"),'
            ' "addanchor2_id" integer NOT NULL'
            ' REFERENCES "custom_add_anchor_table" ("id"),'
            ' UNIQUE ("testmodel_id", "addanchor2_id")'
            ');'
            % get_field_suffix('AutoField'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'testmodel_id'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("addanchor2_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'addanchor2_id'),
        ],

        'AddManyToManySelf': [
            'CREATE TABLE "tests_testmodel_added_field" '
            '("id" integer NOT NULL PRIMARY KEY%s,'
            ' "from_testmodel_id" integer NOT NULL'
            ' REFERENCES "tests_testmodel" ("id"),'
            ' "to_testmodel_id" integer NOT NULL'
            ' REFERENCES "tests_testmodel" ("id"),'
            ' UNIQUE ("from_testmodel_id", "to_testmodel_id")'
            ');'
            % get_field_suffix('AutoField'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("from_testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'from_testmodel_id'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("to_testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'to_testmodel_id'),
        ],
    })
else:
    add_field.update({
        'AddManyToManyDatabaseTableModel': [
            'CREATE TABLE "tests_testmodel_added_field" (',
            '    "id" integer NOT NULL PRIMARY KEY%s,'
            % get_field_suffix('AutoField'),

            '    "testmodel_id" integer NOT NULL,',
            '    "addanchor1_id" integer NOT NULL,',
            '    UNIQUE ("testmodel_id", "addanchor1_id")',
            ')',
            ';',
        ],

        'AddManyToManyNonDefaultDatabaseTableModel': [
            'CREATE TABLE "tests_testmodel_added_field" (',
            '    "id" integer NOT NULL PRIMARY KEY%s,'
            % get_field_suffix('AutoField'),

            '    "testmodel_id" integer NOT NULL,',
            '    "addanchor2_id" integer NOT NULL,',
            '    UNIQUE ("testmodel_id", "addanchor2_id")',
            ')',
            ';',
        ],

        'AddManyToManySelf': [
            'CREATE TABLE "tests_testmodel_added_field" (',
            '    "id" integer NOT NULL PRIMARY KEY%s,'
            % get_field_suffix('AutoField'),

            '    "from_testmodel_id" integer NOT NULL,',
            '    "to_testmodel_id" integer NOT NULL,',
            '    UNIQUE ("from_testmodel_id", "to_testmodel_id")',
            ')',
            ';',
        ],
    })

delete_field = {
    'DefaultNamedColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "non-default_db_column" integer NOT NULL,'
        ' "int_field3" integer NOT NULL UNIQUE,'
        ' "fk_field1_id" integer NOT NULL'
        ' REFERENCES "tests_deleteanchor1" ("id")'
        ' DEFERRABLE INITIALLY DEFERRED);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("my_id", "char_field", "non-default_db_column", "int_field3",'
        ' "fk_field1_id")'
        ' SELECT "my_id", "char_field", "non-default_db_column",'
        ' "int_field3", "fk_field1_id"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" ("fk_field1_id");'
        % generate_index_name('tests_testmodel', 'fk_field1_id',
                              'fk_field1'),
    ],

    'NonDefaultNamedColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "int_field3" integer NOT NULL UNIQUE,'
        ' "fk_field1_id" integer NOT NULL'
        ' REFERENCES "tests_deleteanchor1" ("id")'
        ' DEFERRABLE INITIALLY DEFERRED);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("my_id", "char_field", "int_field", "int_field3", "fk_field1_id")'
        ' SELECT "my_id", "char_field", "int_field", "int_field3",'
        ' "fk_field1_id"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" ("fk_field1_id");'
        % generate_index_name('tests_testmodel', 'fk_field1_id',
                              'fk_field1'),
    ],

    'ConstrainedColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "non-default_db_column" integer NOT NULL,'
        ' "fk_field1_id" integer NOT NULL'
        ' REFERENCES "tests_deleteanchor1" ("id")'
        ' DEFERRABLE INITIALLY DEFERRED);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("my_id", "char_field", "int_field", "non-default_db_column",'
        ' "fk_field1_id")'
        ' SELECT "my_id", "char_field", "int_field", "non-default_db_column",'
        ' "fk_field1_id"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" ("fk_field1_id");'
        % generate_index_name('tests_testmodel', 'fk_field1_id',
                              'fk_field1'),
    ],

    'DefaultManyToManyModel': [
        'DROP TABLE "tests_testmodel_m2m_field1";',
    ],

    'NonDefaultManyToManyModel': [
        'DROP TABLE "non-default_m2m_table";',
    ],

    'DeleteForeignKeyModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "non-default_db_column" integer NOT NULL,'
        ' "int_field3" integer NOT NULL UNIQUE);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("my_id", "char_field", "int_field", "non-default_db_column",'
        ' "int_field3")'
        ' SELECT "my_id", "char_field", "int_field", "non-default_db_column",'
        ' "int_field3"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'DeleteColumnCustomTableModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "alt_value" varchar(20) NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("id", "alt_value")'
        ' SELECT "id", "alt_value"'
        ' FROM "custom_table_name";',

        'DROP TABLE "custom_table_name";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "custom_table_name";',
    ],
}

change_field = {
    'SetNotNullChangeModelWithConstant': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "alt_pk" integer NOT NULL,'
        ' "custom_db_column" integer NOT NULL,'
        ' "int_field1" integer NOT NULL,'
        ' "int_field2" integer NOT NULL,'
        ' "int_field3" integer NOT NULL UNIQUE,'
        ' "int_field4" integer NOT NULL,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "char_field1" varchar(25) NOT NULL,'
        ' "char_field2" varchar(30) NOT NULL);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("my_id", "alt_pk", "custom_db_column", "int_field1", "int_field2",'
        ' "int_field3", "int_field4", "char_field", "char_field1",'
        ' "char_field2")'
        ' SELECT "my_id", "alt_pk", "custom_db_column", "int_field1",'
        ' "int_field2", "int_field3", "int_field4", "char_field",'
        ' "char_field1", "char_field2"'
        ' FROM "tests_testmodel";',

        'UPDATE "TEMP_TABLE" SET "char_field1" = \'abc\\\'s xyz\';',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" ("int_field1");'
        % generate_index_name('tests_testmodel', 'int_field1'),
    ],

    'SetNotNullChangeModelWithCallable': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "alt_pk" integer NOT NULL,'
        ' "custom_db_column" integer NOT NULL,'
        ' "int_field1" integer NOT NULL,'
        ' "int_field2" integer NOT NULL,'
        ' "int_field3" integer NOT NULL UNIQUE,'
        ' "int_field4" integer NOT NULL,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "char_field1" varchar(25) NOT NULL,'
        ' "char_field2" varchar(30) NOT NULL);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("my_id", "alt_pk", "custom_db_column", "int_field1", "int_field2",'
        ' "int_field3", "int_field4", "char_field", "char_field1",'
        ' "char_field2")'
        ' SELECT "my_id", "alt_pk", "custom_db_column", "int_field1",'
        ' "int_field2", "int_field3", "int_field4", "char_field",'
        ' "char_field1", "char_field2"'
        ' FROM "tests_testmodel";',

        'UPDATE "TEMP_TABLE" SET "char_field1" = "char_field";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" ("int_field1");'
        % generate_index_name('tests_testmodel', 'int_field1'),
    ],

    'SetNullChangeModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "alt_pk" integer NOT NULL,'
        ' "custom_db_column" integer NOT NULL,'
        ' "int_field1" integer NOT NULL,'
        ' "int_field2" integer NOT NULL,'
        ' "int_field3" integer NOT NULL UNIQUE,'
        ' "int_field4" integer NOT NULL,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "char_field1" varchar(25) NULL,'
        ' "char_field2" varchar(30) NULL);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("my_id", "alt_pk", "custom_db_column", "int_field1", "int_field2",'
        ' "int_field3", "int_field4", "char_field", "char_field1",'
        ' "char_field2")'
        ' SELECT "my_id", "alt_pk", "custom_db_column", "int_field1",'
        ' "int_field2", "int_field3", "int_field4", "char_field",'
        ' "char_field1", "char_field2"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" ("int_field1");'
        % generate_index_name('tests_testmodel', 'int_field1'),
    ],

    'NoOpChangeModel': [],

    'IncreasingMaxLengthChangeModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "alt_pk" integer NOT NULL,'
        ' "custom_db_column" integer NOT NULL,'
        ' "int_field1" integer NOT NULL,'
        ' "int_field2" integer NOT NULL,'
        ' "int_field3" integer NOT NULL UNIQUE,'
        ' "int_field4" integer NOT NULL,'
        ' "char_field" varchar(45) NOT NULL,'
        ' "char_field1" varchar(25) NULL,'
        ' "char_field2" varchar(30) NOT NULL);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("my_id", "alt_pk", "custom_db_column", "int_field1", "int_field2",'
        ' "int_field3", "int_field4", "char_field", "char_field1",'
        ' "char_field2")'
        ' SELECT "my_id", "alt_pk", "custom_db_column", "int_field1",'
        ' "int_field2", "int_field3", "int_field4", "char_field",'
        ' "char_field1", "char_field2"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" ("int_field1");'
        % generate_index_name('tests_testmodel', 'int_field1'),
    ],

    'DecreasingMaxLengthChangeModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "alt_pk" integer NOT NULL,'
        ' "custom_db_column" integer NOT NULL,'
        ' "int_field1" integer NOT NULL,'
        ' "int_field2" integer NOT NULL,'
        ' "int_field3" integer NOT NULL UNIQUE,'
        ' "int_field4" integer NOT NULL,'
        ' "char_field" varchar(1) NOT NULL,'
        ' "char_field1" varchar(25) NULL,'
        ' "char_field2" varchar(30) NOT NULL);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("my_id", "alt_pk", "custom_db_column", "int_field1", "int_field2",'
        ' "int_field3", "int_field4", "char_field", "char_field1",'
        ' "char_field2")'
        ' SELECT "my_id", "alt_pk", "custom_db_column", "int_field1",'
        ' "int_field2", "int_field3", "int_field4", "char_field",'
        ' "char_field1", "char_field2"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" ("int_field1");'
        % generate_index_name('tests_testmodel', 'int_field1'),
    ],

    'DBColumnChangeModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "alt_pk" integer NOT NULL,'
        ' "customised_db_column" integer NOT NULL,'
        ' "int_field1" integer NOT NULL,'
        ' "int_field2" integer NOT NULL,'
        ' "int_field3" integer NOT NULL UNIQUE,'
        ' "int_field4" integer NOT NULL,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "char_field1" varchar(25) NULL,'
        ' "char_field2" varchar(30) NOT NULL);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("my_id", "alt_pk", "customised_db_column", "int_field1",'
        ' "int_field2", "int_field3", "int_field4", "char_field",'
        ' "char_field1", "char_field2")'
        ' SELECT "my_id", "alt_pk", "custom_db_column", "int_field1",'
        ' "int_field2", "int_field3", "int_field4", "char_field",'
        ' "char_field1", "char_field2"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" ("int_field1");'
        % generate_index_name('tests_testmodel', 'int_field1'),
    ],

    'M2MDBTableChangeModel': [
        'ALTER TABLE "change_field_non-default_m2m_table"'
        ' RENAME TO "custom_m2m_db_table_name";',
    ],

    'AddDBIndexChangeModel': [
        'CREATE INDEX "%s" ON "tests_testmodel" ("int_field2");'
        % generate_index_name('tests_testmodel', 'int_field2'),
    ],

    'AddDBIndexNoOpChangeModel': [],

    'RemoveDBIndexChangeModel': [
        'DROP INDEX "%s";'
        % generate_index_name('tests_testmodel', 'int_field1')
    ],

    'RemoveDBIndexNoOpChangeModel': [],

    'AddUniqueChangeModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "alt_pk" integer NOT NULL,'
        ' "custom_db_column" integer NOT NULL,'
        ' "int_field1" integer NOT NULL,'
        ' "int_field2" integer NOT NULL,'
        ' "int_field3" integer NOT NULL UNIQUE,'
        ' "int_field4" integer NOT NULL UNIQUE,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "char_field1" varchar(25) NULL,'
        ' "char_field2" varchar(30) NOT NULL);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("my_id", "alt_pk", "custom_db_column", "int_field1", "int_field2",'
        ' "int_field3", "int_field4", "char_field", "char_field1",'
        ' "char_field2")'
        ' SELECT "my_id", "alt_pk", "custom_db_column", "int_field1",'
        ' "int_field2", "int_field3", "int_field4", "char_field",'
        ' "char_field1", "char_field2"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" ("int_field1");'
        % generate_index_name('tests_testmodel', 'int_field1'),
    ],

    'RemoveUniqueChangeModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "alt_pk" integer NOT NULL,'
        ' "custom_db_column" integer NOT NULL,'
        ' "int_field1" integer NOT NULL,'
        ' "int_field2" integer NOT NULL,'
        ' "int_field3" integer NOT NULL,'
        ' "int_field4" integer NOT NULL,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "char_field1" varchar(25) NULL,'
        ' "char_field2" varchar(30) NOT NULL);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("my_id", "alt_pk", "custom_db_column", "int_field1", "int_field2",'
        ' "int_field3", "int_field4", "char_field", "char_field1",'
        ' "char_field2")'
        ' SELECT "my_id", "alt_pk", "custom_db_column", "int_field1",'
        ' "int_field2", "int_field3", "int_field4", "char_field",'
        ' "char_field1", "char_field2"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" ("int_field1");'
        % generate_index_name('tests_testmodel', 'int_field1'),
    ],

    'MultiAttrChangeModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "alt_pk" integer NOT NULL,'
        ' "custom_db_column2" integer NOT NULL,'
        ' "int_field1" integer NOT NULL,'
        ' "int_field2" integer NOT NULL,'
        ' "int_field3" integer NOT NULL UNIQUE,'
        ' "int_field4" integer NOT NULL,'
        ' "char_field" varchar(35) NOT NULL,'
        ' "char_field1" varchar(25) NULL,'
        ' "char_field2" varchar(30) NULL);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("my_id", "alt_pk", "custom_db_column2", "int_field1", "int_field2",'
        ' "int_field3", "int_field4", "char_field", "char_field1",'
        ' "char_field2")'
        ' SELECT "my_id", "alt_pk", "custom_db_column", "int_field1",'
        ' "int_field2", "int_field3", "int_field4", "char_field",'
        ' "char_field1", "char_field2"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" ("int_field1");'
        % generate_index_name('tests_testmodel', 'int_field1'),
    ],

    'MultiAttrSingleFieldChangeModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "alt_pk" integer NOT NULL,'
        ' "custom_db_column" integer NOT NULL,'
        ' "int_field1" integer NOT NULL,'
        ' "int_field2" integer NOT NULL,'
        ' "int_field3" integer NOT NULL UNIQUE,'
        ' "int_field4" integer NOT NULL,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "char_field1" varchar(25) NULL,'
        ' "char_field2" varchar(35) NULL);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("my_id", "alt_pk", "custom_db_column", "int_field1", "int_field2",'
        ' "int_field3", "int_field4", "char_field", "char_field1",'
        ' "char_field2")'
        ' SELECT "my_id", "alt_pk", "custom_db_column", "int_field1",'
        ' "int_field2", "int_field3", "int_field4", "char_field",'
        ' "char_field1", "char_field2"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" ("int_field1");'
        % generate_index_name('tests_testmodel', 'int_field1'),
    ],

    'RedundantAttrsChangeModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "alt_pk" integer NOT NULL,'
        ' "custom_db_column3" integer NOT NULL,'
        ' "int_field1" integer NOT NULL,'
        ' "int_field2" integer NOT NULL,'
        ' "int_field3" integer NOT NULL UNIQUE,'
        ' "int_field4" integer NOT NULL,'
        ' "char_field" varchar(35) NOT NULL,'
        ' "char_field1" varchar(25) NULL,'
        ' "char_field2" varchar(30) NULL);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("my_id", "alt_pk", "custom_db_column3", "int_field1", "int_field2",'
        ' "int_field3", "int_field4", "char_field", "char_field1",'
        ' "char_field2")'
        ' SELECT "my_id", "alt_pk", "custom_db_column", "int_field1",'
        ' "int_field2", "int_field3", "int_field4", "char_field",'
        ' "char_field1", "char_field2"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" ("int_field1");'
        % generate_index_name('tests_testmodel', 'int_field1'),
    ],
}

delete_model = {
    'BasicModel': [
        'DROP TABLE "tests_basicmodel";',
    ],

    'BasicWithM2MModel': [
        'DROP TABLE "tests_basicwithm2mmodel_m2m";',

        'DROP TABLE "tests_basicwithm2mmodel";',
    ],

    'CustomTableModel': [
        'DROP TABLE "custom_table_name";',
    ],

    'CustomTableWithM2MModel': [
        'DROP TABLE "another_custom_table_name_m2m";',

        'DROP TABLE "another_custom_table_name";',
    ],
}

rename_model = {
    'RenameModel': [
        'ALTER TABLE "tests_testmodel" RENAME TO "tests_destmodel";',
    ],

    'RenameModelSameTable': [],

    'RenameModelForeignKeys': [
        'ALTER TABLE "tests_testmodel" RENAME TO "tests_destmodel";',
    ],

    'RenameModelForeignKeysSameTable': [],

    'RenameModelManyToManyField': [
        'ALTER TABLE "tests_testmodel" RENAME TO "tests_destmodel";',
    ],

    'RenameModelManyToManyFieldSameTable': [],
}

delete_application = {
    'DeleteApplication': [
        'DROP TABLE "tests_testmodel_anchor_m2m";',
        'DROP TABLE "tests_testmodel";',
        'DROP TABLE "tests_appdeleteanchor1";',
        'DROP TABLE "app_delete_custom_add_anchor_table";',
        'DROP TABLE "app_delete_custom_table_name";',
    ],

    'DeleteApplicationWithoutDatabase': [],
}

rename_field = {
    'RenameColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "renamed_field" integer NOT NULL,'
        ' "custom_db_col_name" integer NOT NULL,'
        ' "custom_db_col_name_indexed" integer NOT NULL,'
        ' "fk_field_id" integer NOT NULL'
        ' REFERENCES "tests_renameanchor1" ("id")'
        ' DEFERRABLE INITIALLY DEFERRED);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("id", "char_field", "renamed_field", "custom_db_col_name",'
        ' "custom_db_col_name_indexed", "fk_field_id")'
        ' SELECT "id", "char_field", "int_field", "custom_db_col_name",'
        ' "custom_db_col_name_indexed", "fk_field_id"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel"'
        ' ("custom_db_col_name_indexed");'
        % generate_index_name('tests_testmodel', 'custom_db_col_name_indexed',
                              'int_field_named_indexed'),

        'CREATE INDEX "%s" ON "tests_testmodel" ("fk_field_id");'
        % generate_index_name('tests_testmodel', 'fk_field_id', 'fk_field'),
    ],

    'RenameColumnWithTableNameModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "renamed_field" integer NOT NULL,'
        ' "custom_db_col_name" integer NOT NULL,'
        ' "custom_db_col_name_indexed" integer NOT NULL,'
        ' "fk_field_id" integer NOT NULL'
        ' REFERENCES "tests_renameanchor1" ("id")'
        ' DEFERRABLE INITIALLY DEFERRED);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("id", "char_field", "renamed_field", "custom_db_col_name",'
        ' "custom_db_col_name_indexed", "fk_field_id")'
        ' SELECT "id", "char_field", "int_field", "custom_db_col_name",'
        ' "custom_db_col_name_indexed", "fk_field_id"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel"'
        ' ("custom_db_col_name_indexed");'
        % generate_index_name('tests_testmodel', 'custom_db_col_name_indexed',
                              'int_field_named_indexed'),

        'CREATE INDEX "%s" ON "tests_testmodel" ("fk_field_id");'
        % generate_index_name('tests_testmodel', 'fk_field_id', 'fk_field'),
    ],

    'RenamePrimaryKeyColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_pk_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "custom_db_col_name" integer NOT NULL,'
        ' "custom_db_col_name_indexed" integer NOT NULL,'
        ' "fk_field_id" integer NOT NULL'
        ' REFERENCES "tests_renameanchor1" ("id")'
        ' DEFERRABLE INITIALLY DEFERRED);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("my_pk_id", "char_field", "int_field", "custom_db_col_name",'
        ' "custom_db_col_name_indexed", "fk_field_id")'
        ' SELECT "id", "char_field", "int_field", "custom_db_col_name",'
        ' "custom_db_col_name_indexed", "fk_field_id"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel"'
        ' ("custom_db_col_name_indexed");'
        % generate_index_name('tests_testmodel', 'custom_db_col_name_indexed',
                              'int_field_named_indexed'),

        'CREATE INDEX "%s" ON "tests_testmodel" ("fk_field_id");'
        % generate_index_name('tests_testmodel', 'fk_field_id', 'fk_field'),
    ],

    'RenameForeignKeyColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("int_field" integer NOT NULL,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "custom_db_col_name" integer NOT NULL,'
        ' "custom_db_col_name_indexed" integer NOT NULL,'
        ' "renamed_field_id" integer NOT NULL'
        ' REFERENCES "tests_renameanchor1" ("id")'
        ' DEFERRABLE INITIALLY DEFERRED,'
        ' "id" integer NOT NULL UNIQUE PRIMARY KEY);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("renamed_field", "char_field", "int_field",'
        ' "custom_db_col_name_indexed", "fk_field_id", "id")'
        ' SELECT "custom_db_col_name", "char_field", "int_field",'
        ' "custom_db_col_name_indexed", "fk_field_id", "id"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" '
        ' ("custom_db_col_name_indexed");'
        % generate_index_name('tests_testmodel', 'custom_db_col_name_indexed'),

        'CREATE INDEX "%s" ON "tests_testmodel" ("renamed_field_id");'
        % generate_index_name('tests_testmodel', 'renamed_field_id'),
    ],

    'RenameNonDefaultColumnNameModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "renamed_field" integer NOT NULL,'
        ' "custom_db_col_name_indexed" integer NOT NULL,'
        ' "fk_field_id" integer NOT NULL'
        ' REFERENCES "tests_renameanchor1" ("id")'
        ' DEFERRABLE INITIALLY DEFERRED);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("id", "char_field", "int_field", "renamed_field",'
        ' "custom_db_col_name_indexed", "fk_field_id")'
        ' SELECT "id", "char_field", "int_field", "custom_db_col_name",'
        ' "custom_db_col_name_indexed", "fk_field_id"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel"'
        ' ("custom_db_col_name_indexed");'
        % generate_index_name('tests_testmodel', 'custom_db_col_name_indexed',
                              'int_field_named_indexed'),

        'CREATE INDEX "%s" ON "tests_testmodel" ("fk_field_id");'
        % generate_index_name('tests_testmodel', 'fk_field_id', 'fk_field'),
    ],

    'RenameNonDefaultColumnNameToNonDefaultNameModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "non-default_column_name" integer NOT NULL,'
        ' "custom_db_col_name_indexed" integer NOT NULL,'
        ' "fk_field_id" integer NOT NULL'
        ' REFERENCES "tests_renameanchor1" ("id")'
        ' DEFERRABLE INITIALLY DEFERRED);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("id", "char_field", "int_field", "non-default_column_name",'
        ' "custom_db_col_name_indexed", "fk_field_id")'
        ' SELECT "id", "char_field", "int_field", "custom_db_col_name",'
        ' "custom_db_col_name_indexed", "fk_field_id"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel"'
        ' ("custom_db_col_name_indexed");'
        % generate_index_name('tests_testmodel', 'custom_db_col_name_indexed',
                              'int_field_named_indexed'),

        'CREATE INDEX "%s" ON "tests_testmodel" ("fk_field_id");'
        % generate_index_name('tests_testmodel', 'fk_field_id', 'fk_field'),
    ],

    'RenameNonDefaultColumnNameToNonDefaultNameAndTableModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "int_field" integer NOT NULL,'
        ' "non-default_column_name2" integer NOT NULL,'
        ' "custom_db_col_name_indexed" integer NOT NULL,'
        ' "fk_field_id" integer NOT NULL'
        ' REFERENCES "tests_renameanchor1" ("id")'
        ' DEFERRABLE INITIALLY DEFERRED);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("id", "char_field", "int_field", "non-default_column_name2",'
        ' "custom_db_col_name_indexed", "fk_field_id")'
        ' SELECT "id", "char_field", "int_field", "custom_db_col_name",'
        ' "custom_db_col_name_indexed", "fk_field_id"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel"'
        ' ("custom_db_col_name_indexed");'
        % generate_index_name('tests_testmodel', 'custom_db_col_name_indexed',
                              'int_field_named_indexed'),

        'CREATE INDEX "%s" ON "tests_testmodel" ("fk_field_id");'
        % generate_index_name('tests_testmodel', 'fk_field_id', 'fk_field'),
    ],

    'RenameColumnCustomTableModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "renamed_field" integer NOT NULL,'
        ' "alt_value" varchar(20) NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("id", "renamed_field", "alt_value")'
        ' SELECT "id", "value", "alt_value"'
        ' FROM "custom_rename_table_name";',

        'DROP TABLE "custom_rename_table_name";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "custom_rename_table_name";',
    ],

    'RenameManyToManyTableModel': [
        'ALTER TABLE "tests_testmodel_m2m_field"'
        ' RENAME TO "tests_testmodel_renamed_field";',
    ],

    'RenameManyToManyTableWithColumnNameModel': [
        'ALTER TABLE "tests_testmodel_m2m_field"'
        ' RENAME TO "tests_testmodel_renamed_field";',
    ],

    'RenameNonDefaultManyToManyTableModel': [
        'ALTER TABLE "non-default_db_table"'
        ' RENAME TO "tests_testmodel_renamed_field";',
    ],
}

sql_mutation = {
    'AddFirstTwoFields': [
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field1" integer NULL;',

        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field2" integer NULL;',
    ],

    'AddThirdField': [
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field3" integer NULL;',
    ],

    'SQLMutationOutput': [
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field1" integer NULL;',

        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field2" integer NULL;',

        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field3" integer NULL;',
    ],
}

generics = {
    'DeleteColumnModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "int_field" integer NOT NULL,'
        ' "content_type_id" integer NOT NULL'
        ' REFERENCES "django_content_type" ("id")'
        ' DEFERRABLE INITIALLY DEFERRED,'
        ' "object_id" integer unsigned NOT NULL);',

        'INSERT INTO "TEMP_TABLE"'
        ' ("id", "int_field", "content_type_id", "object_id")'
        ' SELECT "id", "int_field", "content_type_id", "object_id"'
        ' FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" ("content_type_id");'
        % generate_index_name('tests_testmodel', 'content_type_id',
                              'content_type'),

        'CREATE INDEX "%s" ON "tests_testmodel" ("object_id");'
        % generate_index_name('tests_testmodel', 'object_id'),
    ],
}

inheritance = {
    'AddToChildModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("int_field" integer NOT NULL,'
        ' "id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "added_field" integer NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("int_field", "id", "char_field")'
        ' SELECT "int_field", "id", "char_field"'
        ' FROM "tests_childmodel";',

        'UPDATE "TEMP_TABLE" SET "added_field" = 42;',

        'DROP TABLE "tests_childmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_childmodel";',
    ],

    'DeleteFromChildModel': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("id", "char_field")'
        ' SELECT "id", "char_field"'
        ' FROM "tests_childmodel";',

        'DROP TABLE "tests_childmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_childmodel";',
    ],
}

unique_together = {
    'setting_from_empty': [
        'CREATE UNIQUE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field1", "char_field1");'
        % generate_unique_constraint_name('tests_testmodel',
                                          ['int_field1', 'char_field1']),
    ],

    'append_list': [
        'CREATE UNIQUE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field2", "char_field2");'
        % generate_unique_constraint_name('tests_testmodel',
                                          ['int_field2', 'char_field2']),
    ],

    'set_remove': [
        'CREATE UNIQUE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field1", "char_field1");'
        % generate_unique_constraint_name('tests_testmodel',
                                          ['int_field1', 'char_field1']),
    ],

    'ignore_missing_indexes': [
        'CREATE UNIQUE INDEX "%s"'
        ' ON "tests_testmodel" ("char_field1", "char_field2");'
        % generate_unique_constraint_name('tests_testmodel',
                                          ['char_field1', 'char_field2']),
    ],

    'upgrade_from_v1_sig': [
        'CREATE UNIQUE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field1", "char_field1");'
        % generate_unique_constraint_name('tests_testmodel',
                                          ['int_field1', 'char_field1']),
    ],
}

if django.VERSION[:2] >= (1, 9):
    # Django >= 1.9
    unique_together.update({
        'replace_list': [
            'DROP INDEX "%s";'
            % generate_unique_constraint_name('tests_testmodel',
                                              ['int_field1', 'char_field1']),

            'CREATE UNIQUE INDEX "%s"'
            ' ON "tests_testmodel" ("int_field2", "char_field2");'
            % generate_unique_constraint_name('tests_testmodel',
                                              ['int_field2', 'char_field2']),
        ],

        'removing': [
            'DROP INDEX "%s";'
            % generate_unique_constraint_name('tests_testmodel',
                                              ['int_field1', 'char_field1']),
        ],
    })
else:
    # Django < 1.9
    unique_together.update({
        'replace_list': [
            'CREATE TABLE "TEMP_TABLE" '
            '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
            ' "int_field1" integer NOT NULL,'
            ' "int_field2" integer NOT NULL,'
            ' "char_field1" varchar(20) NOT NULL,'
            ' "char_field2" varchar(40) NOT NULL);',

            'INSERT INTO "TEMP_TABLE"'
            ' ("id", "int_field1", "int_field2", "char_field1", "char_field2")'
            ' SELECT "id", "int_field1", "int_field2", "char_field1",'
            ' "char_field2" FROM "tests_testmodel";',

            'DROP TABLE "tests_testmodel";',

            'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

            'CREATE UNIQUE INDEX "%s"'
            ' ON "tests_testmodel" ("int_field2", "char_field2");'
            % generate_unique_constraint_name('tests_testmodel',
                                              ['int_field2', 'char_field2']),
        ],

        'removing': [
            'CREATE TABLE "TEMP_TABLE" '
            '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
            ' "int_field1" integer NOT NULL,'
            ' "int_field2" integer NOT NULL,'
            ' "char_field1" varchar(20) NOT NULL,'
            ' "char_field2" varchar(40) NOT NULL);',

            'INSERT INTO "TEMP_TABLE"'
            ' ("id", "int_field1", "int_field2", "char_field1", "char_field2")'
            ' SELECT "id", "int_field1", "int_field2", "char_field1",'
            ' "char_field2" FROM "tests_testmodel";',

            'DROP TABLE "tests_testmodel";',

            'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
        ],
    })

index_together = {
    'setting_from_empty': [
        'CREATE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field1", "char_field1");'
        % generate_index_name('tests_testmodel',
                              ['int_field1', 'char_field1'],
                              index_together=True),
    ],

    'replace_list': [
        'DROP INDEX "%s";'
        % generate_index_name('tests_testmodel',
                              ['int_field1', 'char_field1'],
                              index_together=True),

        'CREATE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field2", "char_field2");'
        % generate_index_name('tests_testmodel',
                              ['int_field2', 'char_field2'],
                              index_together=True),
    ],

    'append_list': [
        'CREATE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field2", "char_field2");'
        % generate_index_name('tests_testmodel',
                              ['int_field2', 'char_field2'],
                              index_together=True),
    ],

    'removing': [
        'DROP INDEX "%s";'
        % generate_index_name('tests_testmodel',
                              ['int_field1', 'char_field1'],
                              index_together=True),
    ],

    'ignore_missing_indexes': [
        'CREATE INDEX "%s"'
        ' ON "tests_testmodel" ("char_field1", "char_field2");'
        % generate_index_name('tests_testmodel',
                              ['char_field1', 'char_field2'],
                              index_together=True),
    ],
}

indexes = {
    'replace_list': [
        'DROP INDEX "%s";'
        % generate_index_name('tests_testmodel', ['int_field1'],
                              model_meta_indexes=True),

        'DROP INDEX "my_custom_index";',

        'CREATE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field2");'
        % generate_index_name('tests_testmodel', ['int_field2'],
                              model_meta_indexes=True),
    ],

    'append_list': [
        'CREATE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field2");'
        % generate_index_name('tests_testmodel', ['int_field2'],
                              model_meta_indexes=True),
    ],

    'removing': [
        'DROP INDEX "%s";'
        % generate_index_name('tests_testmodel', ['int_field1'],
                              model_meta_indexes=True),

        'DROP INDEX "my_custom_index";',
    ],

    'ignore_missing_indexes': [
        'CREATE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field2");'
        % generate_index_name('tests_testmodel', ['int_field2'],
                              model_meta_indexes=True),
    ],
}

if django.VERSION[:2] >= (2, 0):
    indexes.update({
        'setting_from_empty': [
            'CREATE INDEX "%s"'
            ' ON "tests_testmodel" ("int_field1");'
            % generate_index_name('tests_testmodel',
                                  ['int_field1'],
                                  model_meta_indexes=True),

            'CREATE INDEX "my_custom_index"'
            ' ON "tests_testmodel" ("char_field1", "char_field2"DESC);',
        ],
    })
else:
    indexes.update({
        'setting_from_empty': [
            'CREATE INDEX "%s"'
            ' ON "tests_testmodel" ("int_field1");'
            % generate_index_name('tests_testmodel',
                                  ['int_field1'],
                                  model_meta_indexes=True),

            'CREATE INDEX "my_custom_index"'
            ' ON "tests_testmodel" ("char_field1", "char_field2" DESC);',
        ],
    })


preprocessing = {
    'add_change_field': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "added_field" varchar(50) NULL);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "char_field")'
        ' SELECT "my_id", "char_field" FROM "tests_testmodel";',

        'UPDATE "TEMP_TABLE" SET "added_field" = \'bar\';',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'add_change_rename_field': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "renamed_field" varchar(50) NULL);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "char_field")'
        ' SELECT "my_id", "char_field" FROM "tests_testmodel";',

        'UPDATE "TEMP_TABLE" SET "renamed_field" = \'bar\';',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'add_delete_add_field': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "added_field" integer NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "char_field")'
        ' SELECT "my_id", "char_field" FROM "tests_testmodel";',

        'UPDATE "TEMP_TABLE" SET "added_field" = 42;',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'add_delete_add_rename_field': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "renamed_field" integer NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "char_field")'
        ' SELECT "my_id", "char_field" FROM "tests_testmodel";',

        'UPDATE "TEMP_TABLE" SET "renamed_field" = 42;',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'add_rename_change_field': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "renamed_field" varchar(50) NULL);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "char_field")'
        ' SELECT "my_id", "char_field" FROM "tests_testmodel";',

        'UPDATE "TEMP_TABLE" SET "renamed_field" = \'bar\';',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'add_rename_change_rename_change_field': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "renamed_field" varchar(50) NULL);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "char_field")'
        ' SELECT "my_id", "char_field" FROM "tests_testmodel";',

        'UPDATE "TEMP_TABLE" SET "renamed_field" = \'foo\';',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'add_rename_field_with_db_column': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "added_field" varchar(50) NULL);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "char_field")'
        ' SELECT "my_id", "char_field" FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'add_field_rename_model': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "added_field_id" integer NULL'
        ' REFERENCES "tests_reffedpreprocmodel" ("id")'
        ' DEFERRABLE INITIALLY DEFERRED);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "char_field")'
        ' SELECT "my_id", "char_field" FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" ("added_field_id");'
        % generate_index_name('tests_testmodel', 'added_field_id',
                              'added_field'),
    ],

    'add_rename_field_rename_model': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "renamed_field_id" integer NULL'
        ' REFERENCES "tests_reffedpreprocmodel" ("id")'
        ' DEFERRABLE INITIALLY DEFERRED);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "char_field")'
        ' SELECT "my_id", "char_field" FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE INDEX "%s" ON "tests_testmodel" ("renamed_field_id");'
        % generate_index_name('tests_testmodel', 'renamed_field_id',
                              'renamed_field'),
    ],

    'add_sql_delete': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL,'
        ' "added_field" varchar(20) NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "char_field")'
        ' SELECT "my_id", "char_field" FROM "tests_testmodel";',

        'UPDATE "TEMP_TABLE" SET "added_field" = \'foo\';',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        '-- Comment --',

        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "char_field")'
        ' SELECT "my_id", "char_field" FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'change_rename_field': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(20) NULL);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "char_field")'
        ' SELECT "my_id", "char_field" FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "renamed_field" varchar(20) NULL);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "renamed_field")'
        ' SELECT "my_id", "char_field" FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'change_rename_change_rename_field': [
        # Change char_field to length of 30 and allow NULL.
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "char_field" varchar(30) NULL);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "char_field")'
        ' SELECT "my_id", "char_field" FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        # Rename char_field to renamed_field.
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "renamed_field" varchar(30) NULL);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "renamed_field")'
        ' SELECT "my_id", "char_field" FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'delete_char_field': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY);',

        'INSERT INTO "TEMP_TABLE" ("my_id")'
        ' SELECT "my_id" FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'rename_add_field': [
        # Rename char_field to renamed_field.
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "renamed_field" varchar(20) NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "renamed_field")'
        ' SELECT "my_id", "char_field" FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        # Remove NULL from renamed_field.
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "renamed_field" varchar(20) NOT NULL,'
        ' "char_field" varchar(50) NULL);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "renamed_field")'
        ' SELECT "my_id", "renamed_field" FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'rename_change_rename_change_field': [
        # Rename char_field to renamed_field.
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "renamed_field" varchar(20) NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "renamed_field")'
        ' SELECT "my_id", "char_field" FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',

        # Set renamed_field to allow NULL and set length to 50.
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "renamed_field" varchar(50) NULL);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "renamed_field")'
        ' SELECT "my_id", "renamed_field" FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'rename_rename_field': [
        'CREATE TABLE "TEMP_TABLE" '
        '("my_id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "renamed_field" varchar(20) NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("my_id", "renamed_field")'
        ' SELECT "my_id", "char_field" FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'rename_delete_model': [
        'DROP TABLE "tests_testmodel";',
    ],

    'noop': [],
}


evolver = {
    'evolve_app_task': [
        'CREATE TABLE "TEMP_TABLE" '
        '("id" integer NOT NULL UNIQUE PRIMARY KEY,'
        ' "value" varchar(100) NOT NULL);',

        'INSERT INTO "TEMP_TABLE" ("id", "value")'
        ' SELECT "id", "value" FROM "tests_testmodel";',

        'DROP TABLE "tests_testmodel";',

        'ALTER TABLE "TEMP_TABLE" RENAME TO "tests_testmodel";',
    ],

    'purge_app_task': [
        'DROP TABLE "tests_testmodel";',
    ],
}

if django.VERSION[:2] >= (1, 7):
    evolver.update({
        'create_table': [
            'CREATE TABLE "tests_testmodel" '
            '("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,'
            ' "value" varchar(100) NOT NULL);',
        ],
    })
else:
    evolver.update({
        'create_table': [
            'CREATE TABLE "tests_testmodel" (',
            '    "id" integer NOT NULL PRIMARY KEY,',
            '    "value" varchar(100) NOT NULL',
            ')',

            ';',
        ],
    })

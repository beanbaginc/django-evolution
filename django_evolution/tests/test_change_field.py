from django.db import connection, models

from django_evolution.errors import SimulationFailure
from django_evolution.mutations import ChangeField
from django_evolution.tests.base_test_case import EvolutionTestCase
from django_evolution.tests.utils import has_index_with_columns


class ChangeSequenceFieldInitial(object):
    def __init__(self, suffix):
        self.suffix = suffix

    def __call__(self):
        return connection.ops.quote_name('char_field')


class ChangeAnchor1(models.Model):
    value = models.IntegerField()


class ChangeBaseModel(models.Model):
    my_id = models.AutoField(primary_key=True)
    alt_pk = models.IntegerField()
    int_field = models.IntegerField(db_column='custom_db_column')
    int_field1 = models.IntegerField(db_index=True)
    int_field2 = models.IntegerField(db_index=False)
    int_field3 = models.IntegerField(unique=True)
    int_field4 = models.IntegerField(unique=False)
    char_field = models.CharField(max_length=20)
    char_field1 = models.CharField(max_length=25, null=True)
    char_field2 = models.CharField(max_length=30, null=False)
    m2m_field1 = models.ManyToManyField(
        ChangeAnchor1, db_table='change_field_non-default_m2m_table')


class ChangeFieldTests(EvolutionTestCase):
    """Testing ChangeField mutations."""
    sql_mapping_key = 'change_field'
    default_base_model = ChangeBaseModel
    default_extra_models = [
        ('ChangeAnchor1', ChangeAnchor1),
    ]

    def test_set_null_false_without_initial_value_raises_exception(self):
        """Testing ChangeField with setting null=False without initial value"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=False)
            char_field2 = models.CharField(max_length=30, null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')

        self.assertRaisesMessage(
            SimulationFailure,
            ("Cannot change column 'char_field1' on 'tests.TestModel'"
             " without a non-null initial value"),
            lambda: self.perform_evolution_tests(
                DestModel,
                [
                    ChangeField('TestModel', 'char_field1', null=False),
                ],
                ("In model tests.TestModel:\n"
                 "    In field 'char_field1':\n"
                 "        Property 'null' has changed"),
                [
                    "ChangeField('TestModel', 'char_field1',"
                    " initial=<<USER VALUE REQUIRED>>, null=False)",
                ]))

    def test_set_null_false_and_null_initial_value_raises_exception(self):
        """Testing ChangeField with setting null=False and null initial
        value
        """
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=False)
            char_field2 = models.CharField(max_length=30, null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')

        self.assertRaisesMessage(
            SimulationFailure,
            ("Cannot change column 'char_field1' on 'tests.TestModel'"
             " without a non-null initial value"),
            lambda: self.perform_evolution_tests(
                DestModel,
                [
                    ChangeField('TestModel', 'char_field1', null=False,
                                initial=None),
                ],
                ("In model tests.TestModel:\n"
                 "    In field 'char_field1':\n"
                 "        Property 'null' has changed"),
                [
                    "ChangeField('TestModel', 'char_field1',"
                    " initial=<<USER VALUE REQUIRED>>, null=False)",
                ]))

    def test_set_null_false_and_initial_value(self):
        """Testing ChangeField with setting null=False and initial value"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=False)
            char_field2 = models.CharField(max_length=30, null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'char_field1', null=False,
                            initial="abc's xyz"),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'char_field1':\n"
             "        Property 'null' has changed"),
            [
                "ChangeField('TestModel', 'char_field1',"
                " initial=<<USER VALUE REQUIRED>>, null=False)",
            ],
            'SetNotNullChangeModelWithConstant')

    def test_set_null_false_and_initial_callable(self):
        """Testing ChangeField with setting null=False and initial callable"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=False)
            char_field2 = models.CharField(max_length=30, null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField(
                    'TestModel', 'char_field1', null=False,
                    initial=ChangeSequenceFieldInitial(
                        'SetNotNullChangeModel')),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'char_field1':\n"
             "        Property 'null' has changed"),
            [
                "ChangeField('TestModel', 'char_field1',"
                " initial=<<USER VALUE REQUIRED>>, null=False)",
            ],
            'SetNotNullChangeModelWithCallable')

    def test_set_null_true(self):
        """Testing ChangeField with setting null=True"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=True)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'char_field2', initial=None,
                            null=True),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'char_field2':\n"
             "        Property 'null' has changed"),
            [
                "ChangeField('TestModel', 'char_field2',"
                " initial=None, null=True)",
            ],
            'SetNullChangeModel')

    def test_set_null_true_when_true_noop(self):
        """Testing ChangeField with setting null=True when already True
        is noop
        """
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'char_field1', null=True),
            ],
            None,
            [
                "ChangeField('TestModel', 'char_field1', null=True)",
            ],
            'NoOpChangeModel',
            expect_noop=True)

    def test_increase_max_length(self):
        """Testing ChangeField with increasing max_length of CharField"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=45)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'char_field', initial=None,
                            max_length=45),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'char_field':\n"
             "        Property 'max_length' has changed"),
            [
                "ChangeField('TestModel', 'char_field',"
                " initial=None, max_length=45)",
            ],
            'IncreasingMaxLengthChangeModel')

    def test_decrease_max_length(self):
        """Testing ChangeField with decreasing max_length of CharField"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=1)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'char_field', initial=None,
                            max_length=1),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'char_field':\n"
             "        Property 'max_length' has changed"),
            [
                "ChangeField('TestModel', 'char_field',"
                " initial=None, max_length=1)",
            ],
            'DecreasingMaxLengthChangeModel')

    def test_change_db_column(self):
        """Testing ChangeField with setting db_column"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='customised_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'int_field', initial=None,
                            db_column='customised_db_column'),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'int_field':\n"
             "        Property 'db_column' has changed"),
            [
                "ChangeField('TestModel', 'int_field',"
                " initial=None, db_column='customised_db_column')",
            ],
            'DBColumnChangeModel')

    def test_change_m2m_db_table(self):
        """Testing ChangeField with setting db_table on ManyToManyField"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='custom_m2m_db_table_name')

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'm2m_field1', initial=None,
                            db_table='custom_m2m_db_table_name'),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'm2m_field1':\n"
             "        Property 'db_table' has changed"),
            [
                "ChangeField('TestModel', 'm2m_field1',"
                " initial=None, db_table='custom_m2m_db_table_name')",
            ],
            'M2MDBTableChangeModel')

    def test_set_db_index_true(self):
        """Testing ChangeField with setting db_index=True"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=True)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')

        self.assertFalse(has_index_with_columns(
            self.database_sig, 'tests_testmodel', ['int_field2']))

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'int_field2', initial=None,
                            db_index=True),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'int_field2':\n"
             "        Property 'db_index' has changed"),
            [
                "ChangeField('TestModel', 'int_field2', initial=None,"
                " db_index=True)",
            ],
            'AddDBIndexChangeModel')

        self.assertTrue(has_index_with_columns(
            self.test_database_sig, 'tests_testmodel', ['int_field2']))

    def test_set_db_index_false(self):
        """Testing ChangeField with setting db_index=False"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=False)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')

        self.assertTrue(has_index_with_columns(
            self.database_sig, 'tests_testmodel', ['int_field1']))

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'int_field1', initial=None,
                            db_index=False),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'int_field1':\n"
             "        Property 'db_index' has changed"),
            [
                "ChangeField('TestModel', 'int_field1', initial=None,"
                " db_index=False)",
            ],
            'RemoveDBIndexChangeModel')

        self.assertFalse(has_index_with_columns(
            self.test_database_sig, 'tests_testmodel', ['int_field1']))

    def test_set_unique_true(self):
        """Testing ChangeField with setting unique=True"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=True)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')

        self.assertFalse(has_index_with_columns(
            self.database_sig, 'tests_testmodel', ['int_field4'],
            unique=True))

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'int_field4', initial=None,
                            unique=True),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'int_field4':\n"
             "        Property 'unique' has changed"),
            [
                "ChangeField('TestModel', 'int_field4', initial=None,"
                " unique=True)",
            ],
            'AddUniqueChangeModel')

        self.assertTrue(has_index_with_columns(
            self.test_database_sig, 'tests_testmodel', ['int_field4'],
            unique=True))

    def test_set_unique_false(self):
        """Testing ChangeField with setting unique=False"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=False)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')

        self.assertTrue(has_index_with_columns(
            self.database_sig, 'tests_testmodel', ['int_field3'],
            unique=True))

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'int_field3', initial=None,
                            unique=False),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'int_field3':\n"
             "        Property 'unique' has changed"),
            [
                "ChangeField('TestModel', 'int_field3', initial=None,"
                " unique=False)",
            ],
            'RemoveUniqueChangeModel')

        self.assertFalse(has_index_with_columns(
            self.test_database_sig, 'tests_testmodel', ['int_field3'],
            unique=True))

    def test_change_multiple_attrs_multi_fields(self):
        """Testing ChangeField with multiple attributes on different fields"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column2')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=35)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=True)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'char_field2', initial=None,
                            null=True),
                ChangeField('TestModel', 'int_field', initial=None,
                            db_column='custom_db_column2'),
                ChangeField('TestModel', 'char_field', initial=None,
                            max_length=35),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'char_field2':\n"
             "        Property 'null' has changed\n"
             "    In field 'int_field':\n"
             "        Property 'db_column' has changed\n"
             "    In field 'char_field':\n"
             "        Property 'max_length' has changed"),
            [
                "ChangeField('TestModel', 'char_field2', initial=None,"
                " null=True)",

                "ChangeField('TestModel', 'int_field', initial=None,"
                " db_column='custom_db_column2')",

                "ChangeField('TestModel', 'char_field', initial=None,"
                " max_length=35)",
            ],
            'MultiAttrChangeModel')

    def test_change_multiple_attrs_one_field(self):
        """Testing ChangeField with multiple attributes on one field"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=35, null=True)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'char_field2', initial=None,
                            max_length=35, null=True),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'char_field2':\n"
             "        Property 'max_length' has changed\n"
             "        Property 'null' has changed"),
            [
                "ChangeField('TestModel', 'char_field2', initial=None,"
                " max_length=35, null=True)",
            ],
            'MultiAttrSingleFieldChangeModel')

    def test_redundant_attributes(self):
        """Testing ChangeField with redundant attributes"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column3')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=35)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=True)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'char_field2', initial=None,
                            max_length=30, null=True),
                ChangeField('TestModel', 'int_field', initial=None,
                            db_column='custom_db_column3',
                            primary_key=False, unique=False, db_index=False),
                ChangeField('TestModel', 'char_field', initial=None,
                            max_length=35),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'char_field2':\n"
             "        Property 'null' has changed\n"
             "    In field 'int_field':\n"
             "        Property 'db_column' has changed\n"
             "    In field 'char_field':\n"
             "        Property 'max_length' has changed"),
            [
                "ChangeField('TestModel', 'char_field2', initial=None,"
                " null=True)",

                "ChangeField('TestModel', 'int_field', initial=None,"
                " db_column='custom_db_column3')",

                "ChangeField('TestModel', 'char_field', initial=None,"
                " max_length=35)",
            ],
            'RedundantAttrsChangeModel')

    def test_change_field_type(self):
        """Testing ChangeField with field type using same internal_type"""
        class MyIntegerField(models.IntegerField):
            def get_internal_type(self):
                return 'IntegerField'

        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = MyIntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')

        self.perform_evolution_tests(
            DestModel,
            [],
            None,
            None,
            expect_noop=True)

    def test_change_with_custom_database(self):
        """Testing ChangeField with custom database"""
        class DestModel(models.Model):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=False)
            char_field2 = models.CharField(max_length=30, null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'char_field1', null=False,
                            initial="abc's xyz"),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'char_field1':\n"
             "        Property 'null' has changed"),
            [
                "ChangeField('TestModel', 'char_field1',"
                " initial=<<USER VALUE REQUIRED>>, null=False)",
            ],
            'SetNotNullChangeModelWithConstant',
            db_name='db_multi')

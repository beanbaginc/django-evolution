from __future__ import unicode_literals

from datetime import datetime, date

from django.db import connection, models
from django.utils import timezone

from django_evolution.db import EvolutionOperationsMulti
from django_evolution.diff import Diff
from django_evolution.errors import SimulationFailure
from django_evolution.mutations import ChangeField
from django_evolution.mutators import AppMutator
from django_evolution.signature import (AppSignature,
                                        ModelSignature,
                                        ProjectSignature)
from django_evolution.tests.base_test_case import EvolutionTestCase
from django_evolution.tests.decorators import requires_model_field
from django_evolution.tests.models import BaseTestModel


class ChangeSequenceFieldInitial(object):
    def __init__(self, suffix):
        self.suffix = suffix

    def __call__(self):
        return connection.ops.quote_name('char_field')


class ChangeAnchor1(BaseTestModel):
    value = models.IntegerField()


class ChangeBaseModel(BaseTestModel):
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
    dec_field = models.DecimalField(max_digits=5,
                                    decimal_places=2)
    dec_field1 = models.DecimalField(max_digits=6,
                                     decimal_places=3,
                                     null=True)
    dec_field2 = models.DecimalField(max_digits=7,
                                     decimal_places=4,
                                     null=False)
    m2m_field1 = models.ManyToManyField(
        ChangeAnchor1, db_table='change_field_non-default_m2m_table')
    datetime_field1 = models.DateTimeField(null=True)
    datetime_field2 = models.DateTimeField(null=False)
    date_field1 = models.DateField(null=True)
    date_field2 = models.DateField(null=False)


class ChangeFieldTests(EvolutionTestCase):
    """Testing ChangeField mutations."""
    sql_mapping_key = 'change_field'
    default_base_model = ChangeBaseModel
    default_extra_models = [
        ('ChangeAnchor1', ChangeAnchor1),
    ]

    def default_create_test_data(self, db_name):
        """Create test data for the base model.

        Args:
            db_name (unicode):
                The name of the database to create models on.
        """
        model = ChangeBaseModel.objects.using(db_name).create(
            alt_pk=1,
            int_field=2,
            int_field1=3,
            int_field2=4,
            int_field3=5,
            int_field4=6,
            char_field='test1',
            char_field1='test2',
            char_field2='test3',
            dec_field=100.25,
            dec_field1=200.50,
            dec_field2=300.75,
            datetime_field1=datetime(2022, 5, 13, 1, 2, 3,
                                     tzinfo=timezone.utc),
            datetime_field2=datetime(2022, 5, 13, 4, 5, 6,
                                     tzinfo=timezone.utc),
            date_field1=date(2020, 5, 12),
            date_field2=date(2020, 5, 13))

        anchor = ChangeAnchor1.objects.using(db_name).create(value=42)
        model.m2m_field1.add(anchor)

    def test_with_bad_app(self):
        """Testing ChangeField with application not in signature"""
        mutation = ChangeField('TestModel', 'char_field1')

        message = (
            'Cannot change the field "char_field1" on model '
            '"badapp.TestModel". The application could not be found in the '
            'signature.'
        )

        with self.assertRaisesMessage(SimulationFailure, message):
            mutation.run_simulation(app_label='badapp',
                                    project_sig=ProjectSignature(),
                                    database_state=None)

    def test_with_bad_model(self):
        """Testing ChangeField with model not in signature"""
        mutation = ChangeField('TestModel', 'char_field1')

        project_sig = ProjectSignature()
        project_sig.add_app_sig(AppSignature(app_id='tests'))

        message = (
            'Cannot change the field "char_field1" on model '
            '"tests.TestModel". The model could not be found in the '
            'signature.'
        )

        with self.assertRaisesMessage(SimulationFailure, message):
            mutation.run_simulation(app_label='tests',
                                    project_sig=project_sig,
                                    database_state=None)

    def test_with_bad_field(self):
        """Testing ChangeField with field not in signature"""
        mutation = ChangeField('TestModel', 'char_field1')

        model_sig = ModelSignature(model_name='TestModel',
                                   table_name='tests_testmodel')

        app_sig = AppSignature(app_id='tests')
        app_sig.add_model_sig(model_sig)

        project_sig = ProjectSignature()
        project_sig.add_app_sig(app_sig)

        message = (
            'Cannot change the field "char_field1" on model '
            '"tests.TestModel". The field could not be found in the '
            'signature.'
        )

        with self.assertRaisesMessage(SimulationFailure, message):
            mutation.run_simulation(app_label='tests',
                                    project_sig=project_sig,
                                    database_state=None)

    def test_set_null_false_without_initial_value_raises_exception(self):
        """Testing ChangeField with setting null=False without initial value"""
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        message = (
            'Cannot change the field "char_field1" on model '
            '"tests.TestModel". A non-null initial value needs to be '
            'specified in the mutation.'
        )

        with self.assertRaisesMessage(SimulationFailure, message):
            self.perform_evolution_tests(
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
                ])

    def test_set_null_false_and_null_initial_value_raises_exception(self):
        """Testing ChangeField with setting null=False and null initial
        value
        """
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        message = (
            'Cannot change the field "char_field1" on model '
            '"tests.TestModel". A non-null initial value needs to be '
            'specified in the mutation.'
        )

        with self.assertRaisesMessage(SimulationFailure, message):
            self.perform_evolution_tests(
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
                ])

    def test_set_null_false_and_initial_value(self):
        """Testing ChangeField with setting null=False and initial value"""
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

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
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

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

    def test_set_null_datetime_false_and_initial_callable(self):
        """Testing ChangeField with setting DateTimeField null=False and
        initial callable
        """
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=False)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField(
                    'TestModel', 'datetime_field1', null=False,
                    initial=lambda: datetime(2022, 5, 13, 12, 13, 14,
                                             tzinfo=timezone.utc)),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'datetime_field1':\n"
             "        Property 'null' has changed"),
            [
                "ChangeField('TestModel', 'datetime_field1',"
                " initial=<<USER VALUE REQUIRED>>, null=False)",
            ],
            'SetDateTimeNotNullChangeModelWithCallable')

    def test_set_null_date_false_and_initial_callable(self):
        """Testing ChangeField with setting DateTimeField null=False and
        initial callable
        """
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=False)
            date_field2 = models.DateField(null=False)

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField(
                    'TestModel', 'date_field1', null=False,
                    initial=lambda: date(2022, 5, 13)),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'date_field1':\n"
             "        Property 'null' has changed"),
            [
                "ChangeField('TestModel', 'date_field1',"
                " initial=<<USER VALUE REQUIRED>>, null=False)",
            ],
            'SetDateNotNullChangeModelWithCallable')

    def test_set_null_true(self):
        """Testing ChangeField with setting null=True"""
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

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
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

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
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

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
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

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
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

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
                " db_column='customised_db_column', initial=None)",
            ],
            'DBColumnChangeModel')

    def test_change_m2m_db_table(self):
        """Testing ChangeField with setting db_table on ManyToManyField"""
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='custom_m2m_db_table_name')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

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
                " db_table='custom_m2m_db_table_name', initial=None)",
            ],
            'M2MDBTableChangeModel')

    def test_change_m2m_null(self):
        """Testing ChangeField with setting null on ManyToManyField"""
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1,
                db_table='change_field_non-default_m2m_table',
                null=True)
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'm2m_field1', null=True),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'm2m_field1':\n"
             "        Property 'null' has changed"),
            [
                "ChangeField('TestModel', 'm2m_field1', initial=None,"
                " null=True)"
            ],
            'M2MNullChangeModel')

    def test_set_db_index_true(self):
        """Testing ChangeField with setting db_index=True"""
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.assertIsNone(self.database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field2']))

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
                "ChangeField('TestModel', 'int_field2', db_index=True,"
                " initial=None)",
            ],
            'AddDBIndexChangeModel')

        self.assertIsNotNone(self.test_database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field2']))

    def test_set_db_index_true_and_existing_index(self):
        """Testing ChangeField with setting db_index=True and existing index
        in the database
        """
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        evolver = EvolutionOperationsMulti('default',
                                           self.database_state).get_evolver()
        index_name = evolver.get_default_index_name(
            'tests_testmodel', DestModel._meta.get_field('int_field2'))

        self.database_state.add_index(table_name='tests_testmodel',
                                      index_name=index_name,
                                      columns=['int_field2'],
                                      unique=False)

        self.assertIsNotNone(self.database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field2']))

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
                "ChangeField('TestModel', 'int_field2', db_index=True,"
                " initial=None)",
            ],
            'AddDBIndexNoOpChangeModel',
            rescan_indexes=False)

        self.assertIsNotNone(self.test_database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field2']))

    def test_set_db_index_false(self):
        """Testing ChangeField with setting db_index=False"""
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.assertIsNotNone(self.database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field1']))

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
                "ChangeField('TestModel', 'int_field1', db_index=False,"
                " initial=None)",
            ],
            'RemoveDBIndexChangeModel')

        self.assertIsNone(self.test_database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field1']))

    def test_set_unique_true(self):
        """Testing ChangeField with setting unique=True"""
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.assertIsNone(self.database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field4'],
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

        self.assertIsNotNone(self.test_database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field4'],
            unique=True))

    def test_set_unique_false(self):
        """Testing ChangeField with setting unique=False"""
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.assertIsNotNone(self.database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field3'],
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

        self.assertIsNone(self.test_database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field3'],
            unique=True))

    def test_set_db_index_false_and_no_existing_index(self):
        """Testing ChangeField with setting db_index=False without an
        existing index in the database
        """
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.database_state.clear_indexes('tests_testmodel')

        self.assertIsNone(self.database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field1']))

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
                "ChangeField('TestModel', 'int_field1', db_index=False,"
                " initial=None)",
            ],
            'RemoveDBIndexNoOpChangeModel',
            rescan_indexes=False)

        self.assertIsNone(self.test_database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field1']))

    def test_set_db_index_false_unique_true(self):
        """Testing ChangeField with setting db_index=False unique=True"""
        class DestModel(BaseTestModel):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=False, unique=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=False)
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.assertIsNotNone(self.database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field1']))
        self.assertIsNone(self.database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field1'],
            unique=True))

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'int_field1', initial=None,
                            db_index=False, unique=True),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'int_field1':\n"
             "        Property 'db_index' has changed\n"
             "        Property 'unique' has changed"),
            [
                "ChangeField('TestModel', 'int_field1', db_index=False,"
                " initial=None, unique=True)",
            ],
            'RemoveDBIndexAddUniqueChangeModel')

        self.assertIsNone(self.test_database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field1']))
        self.assertIsNotNone(self.test_database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field1'],
            unique=True))

    def test_set_db_index_true_unique_false(self):
        """Testing ChangeField with setting db_index=True unique=False"""
        class DestModel(BaseTestModel):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(db_index=True, unique=False)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=False)
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.assertIsNone(self.database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field3']))
        self.assertIsNotNone(self.database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field3'],
            unique=True))

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'int_field3', initial=None,
                            db_index=True, unique=False),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'int_field3':\n"
             "        Property 'db_index' has changed\n"
             "        Property 'unique' has changed"),
            [
                "ChangeField('TestModel', 'int_field3', db_index=True,"
                " initial=None, unique=False)",
            ],
            'AddDBIndexRemoveUniqueChangeModel')

        self.assertIsNotNone(self.test_database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field3']))
        self.assertIsNone(self.test_database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field3'],
            unique=True))

    def test_set_db_index_true_unique_true(self):
        """Testing ChangeField with setting db_index=True unique=True"""
        class DestModel(BaseTestModel):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(db_index=True, unique=True)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=False)
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.assertIsNone(self.database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field4']))
        self.assertIsNone(self.database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field4'],
            unique=True))

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'int_field4', initial=None,
                            db_index=True, unique=True),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'int_field4':\n"
             "        Property 'db_index' has changed\n"
             "        Property 'unique' has changed"),
            [
                "ChangeField('TestModel', 'int_field4', db_index=True,"
                " initial=None, unique=True)",
            ],
            'AddDBIndexAddUniqueChangeModel')

        self.assertIsNone(self.test_database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field4']))
        self.assertIsNotNone(self.test_database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field4'],
            unique=True))

    def test_set_db_index_false_and_other_changes(self):
        """Testing ChangeField with setting db_index=False with other field
        changes
        """
        class DestModel(BaseTestModel):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=False, null=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=False)
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.assertIsNotNone(self.database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field1']))
        self.assertIsNone(self.database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field1'],
            unique=True))

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'int_field1', initial=None,
                            db_index=False, null=True),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'int_field1':\n"
             "        Property 'db_index' has changed\n"
             "        Property 'null' has changed"),
            [
                "ChangeField('TestModel', 'int_field1', db_index=False,"
                " initial=None, null=True)",
            ],
            'RemoveDBIndexAddNullChangeModel')

        self.assertIsNone(self.test_database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field1']))
        self.assertIsNone(self.test_database_state.find_index(
            table_name='tests_testmodel',
            columns=['int_field1'],
            unique=True))

    def test_with_decimal_field_set_decimal_places(self):
        """Testing ChangeField with DecimalField and setting decimal_places"""
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=2,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1,
                db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'dec_field2', decimal_places=2),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'dec_field2':\n"
             "        Property 'decimal_places' has changed"),
            [
                "ChangeField('TestModel', 'dec_field2', decimal_places=2,"
                " initial=None)"
            ],
            'decimal_field_decimal_places')

    def test_with_decimal_field_set_max_digits(self):
        """Testing ChangeField with DecimalField and setting max_digits"""
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=10,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1,
                db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'dec_field1', max_digits=10),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'dec_field1':\n"
             "        Property 'max_digits' has changed"),
            [
                "ChangeField('TestModel', 'dec_field1', initial=None,"
                " max_digits=10)"
            ],
            'decimal_field_max_digits')

    def test_with_decimal_field_set_decimal_places_and_max_digits(self):
        """Testing ChangeField with DecimalField and setting decimal_places and
        max_digits
        """
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=10,
                                             decimal_places=1,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1,
                db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'dec_field1', max_digits=10,
                            decimal_places=1),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'dec_field1':\n"
             "        Property 'decimal_places' has changed\n"
             "        Property 'max_digits' has changed"),
            [
                "ChangeField('TestModel', 'dec_field1', decimal_places=1,"
                " initial=None, max_digits=10)"
            ],
            'decimal_field_decimal_places_max_digits')

    def test_change_multiple_attrs_multi_fields(self):
        """Testing ChangeField with multiple attributes on different fields"""
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

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
             "    In field 'int_field':\n"
             "        Property 'db_column' has changed\n"
             "    In field 'char_field':\n"
             "        Property 'max_length' has changed\n"
             "    In field 'char_field2':\n"
             "        Property 'null' has changed"),
            [
                "ChangeField('TestModel', 'int_field',"
                " db_column='custom_db_column2', initial=None)",

                "ChangeField('TestModel', 'char_field', initial=None,"
                " max_length=35)",

                "ChangeField('TestModel', 'char_field2', initial=None,"
                " null=True)",
            ],
            'MultiAttrChangeModel')

    def test_change_multiple_attrs_one_field(self):
        """Testing ChangeField with multiple attributes on one field"""
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

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
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'char_field2', initial=None,
                            max_length=30, null=True),
                ChangeField('TestModel', 'int_field', initial=None,
                            db_column='custom_db_column3',
                            unique=False, db_index=False),
                ChangeField('TestModel', 'char_field', initial=None,
                            max_length=35),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'int_field':\n"
             "        Property 'db_column' has changed\n"
             "    In field 'char_field':\n"
             "        Property 'max_length' has changed\n"
             "    In field 'char_field2':\n"
             "        Property 'null' has changed"),
            [
                "ChangeField('TestModel', 'int_field',"
                " db_column='custom_db_column3', initial=None)",

                "ChangeField('TestModel', 'char_field', initial=None,"
                " max_length=35)",

                "ChangeField('TestModel', 'char_field2', initial=None,"
                " null=True)",
            ],
            'RedundantAttrsChangeModel')

    def test_change_field_type(self):
        """Testing ChangeField with field type"""
        class DestModel(BaseTestModel):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.TextField(null=True)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=False)
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'char_field',
                            field_type=models.TextField,
                            null=True),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'char_field':\n"
             "        Property 'field_type' has changed"),
            [
                "ChangeField('TestModel', 'char_field',"
                " field_type=models.TextField, initial=None, null=True)"
            ],
            'field_type')

    def test_change_field_type_with_null_false(self):
        """Testing ChangeField with field type with null changed to False"""
        class DestModel(BaseTestModel):
            my_id = models.AutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.TextField(null=False)
            char_field2 = models.CharField(max_length=30, null=False)
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'char_field1',
                            field_type=models.TextField,
                            initial='test123',
                            null=False),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'char_field1':\n"
             "        Property 'field_type' has changed"),
            [
                "ChangeField('TestModel', 'char_field1',"
                " field_type=models.TextField,"
                " initial=<<USER VALUE REQUIRED>>)"
            ],
            'field_type_null_false')

    @requires_model_field('BigAutoField')
    def test_change_field_type_with_primary_key_bigautofield(self):
        """Testing ChangeField with field type and primary key using
        BigAutoField
        """
        class DestModel(BaseTestModel):
            my_id = models.BigAutoField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=False)
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        # NOTE: This test won't result in any SQL changes on SQLite3, due
        #       to AutoField and BigAutoField mapping to "integer". That's
        #       the reason for the extra test using SmallIntegerField below.
        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'my_id',
                            field_type=models.BigAutoField,
                            primary_key=True,
                            initial=None),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'my_id':\n"
             "        Property 'field_type' has changed"),
            [
                "ChangeField('TestModel', 'my_id',"
                " field_type=models.BigAutoField, initial=None,"
                " primary_key=True)",
            ],
            'field_type_primary_key_bigautofield')

    def test_change_field_type_with_primary_key_smallintfield(self):
        """Testing ChangeField with field type and primary key using
        SmallIntegerField
        """
        class DestModel(BaseTestModel):
            my_id = models.SmallIntegerField(primary_key=True)
            alt_pk = models.IntegerField()
            int_field = models.IntegerField(db_column='custom_db_column')
            int_field1 = models.IntegerField(db_index=True)
            int_field2 = models.IntegerField(db_index=False)
            int_field3 = models.IntegerField(unique=True)
            int_field4 = models.IntegerField(unique=False)
            char_field = models.CharField(max_length=20)
            char_field1 = models.CharField(max_length=25, null=True)
            char_field2 = models.CharField(max_length=30, null=False)
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.perform_evolution_tests(
            DestModel,
            [
                ChangeField('TestModel', 'my_id',
                            field_type=models.SmallIntegerField,
                            primary_key=True,
                            initial=None),
            ],
            ("In model tests.TestModel:\n"
             "    In field 'my_id':\n"
             "        Property 'field_type' has changed"),
            [
                "ChangeField('TestModel', 'my_id',"
                " field_type=models.SmallIntegerField, initial=None,"
                " primary_key=True)",
            ],
            'field_type_primary_key_smallintegerfield')

    def test_change_field_type_same_internal_type(self):
        """Testing ChangeField with field type using same internal_type"""
        class MyIntegerField(models.IntegerField):
            def get_internal_type(self):
                return 'IntegerField'

        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.perform_evolution_tests(
            DestModel,
            [],
            None,
            None,
            expect_noop=True)

    def test_change_with_custom_database(self):
        """Testing ChangeField with custom database"""
        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

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

    def test_change_with_add_same_name_other_model(self):
        """Testing ChangeField with same field name as that added in
        another model
        """
        class OtherModel(BaseTestModel):
            int_field = models.IntegerField()
            test_field = models.CharField(max_length=32, null=True)

        class OtherDestModel(BaseTestModel):
            int_field = models.IntegerField()
            test_field = models.CharField(max_length=32, null=False)

        class DestModel(BaseTestModel):
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
            dec_field = models.DecimalField(max_digits=5,
                                            decimal_places=2)
            dec_field1 = models.DecimalField(max_digits=6,
                                             decimal_places=3,
                                             null=True)
            dec_field2 = models.DecimalField(max_digits=7,
                                             decimal_places=4,
                                             null=False)
            m2m_field1 = models.ManyToManyField(
                ChangeAnchor1, db_table='change_field_non-default_m2m_table')
            test_field = models.CharField(max_length=32, null=False)
            datetime_field1 = models.DateTimeField(null=True)
            datetime_field2 = models.DateTimeField(null=False)
            date_field1 = models.DateField(null=True)
            date_field2 = models.DateField(null=False)

        self.set_base_model(
            self.default_base_model,
            pre_extra_models=[
                ('OtherModel', OtherModel),
                ('ChangeAnchor1', ChangeAnchor1)
            ])

        end, end_sig = self.make_end_signatures(DestModel, 'TestModel')
        end2, end_sig2 = self.make_end_signatures(OtherDestModel, 'OtherModel')

        end.update(end2)

        end_app_sig = end_sig.get_app_sig('tests')
        end_app_sig2 = end_sig2.get_app_sig('tests')

        for model_sig in end_app_sig2.model_sigs:
            end_app_sig.add_model_sig(model_sig.clone())

        d = self.perform_diff_test(
            end_sig,
            ("In model tests.OtherModel:\n"
             "    In field 'test_field':\n"
             "        Property 'null' has changed\n"
             "In model tests.TestModel:\n"
             "    Field 'test_field' has been added"),
            [
                "ChangeField('OtherModel', 'test_field',"
                " initial=<<USER VALUE REQUIRED>>, null=False)",

                "AddField('TestModel', 'test_field', models.CharField,"
                " initial=<<USER VALUE REQUIRED>>, max_length=32)",
            ])

        test_sig = self.start_sig.clone()
        app_mutator = AppMutator(app_label='tests',
                                 project_sig=test_sig,
                                 database_state=self.database_state)
        evolutions = d.evolution()['tests']
        app_mutator.run_mutations(evolutions)

        d = Diff(self.start_sig, test_sig)

        self.assertEqual(
            str(d),
            ("In model tests.OtherModel:\n"
             "    In field 'test_field':\n"
             "        Property 'null' has changed\n"
             "In model tests.TestModel:\n"
             "    Field 'test_field' has been added"))

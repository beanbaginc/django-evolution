from django_evolution import is_multi_db
from django_evolution.tests.add_field import tests as add_field_tests
from django_evolution.tests.change_field import tests as change_field_tests
from django_evolution.tests.delete_app import tests as delete_app_tests
from django_evolution.tests.delete_field import tests as delete_field_tests
from django_evolution.tests.delete_model import tests as delete_model_tests
from django_evolution.tests.generics import tests as generics_tests
from django_evolution.tests.inheritance import tests as inheritance_tests
from django_evolution.tests.ordering import tests as ordering_tests
from django_evolution.tests.rename_field import tests as rename_field_tests
from django_evolution.tests.signature import tests as signature_tests
from django_evolution.tests.sql_mutation import tests as sql_mutation_tests


# Define doctests
__test__ = {
    'signature': signature_tests,
    'add_field': add_field_tests,
    'delete_field': delete_field_tests,
    'delete_model': delete_model_tests,
    'delete_app': delete_app_tests,
    'rename_field': rename_field_tests,
    'change_field': change_field_tests,
    'sql_mutation': sql_mutation_tests,
    'ordering': ordering_tests,
    'generics': generics_tests,
    'inheritance': inheritance_tests
}

if is_multi_db():
    from multi_db import tests as multi_db_tests
    __test__['multi_db'] = multi_db_tests

from django_evolution import is_multi_db
from django_evolution.tests.signature import tests as signature_tests


# Define doctests
__test__ = {
    'signature': signature_tests,
}

if is_multi_db():
    from multi_db import tests as multi_db_tests
    __test__['multi_db'] = multi_db_tests

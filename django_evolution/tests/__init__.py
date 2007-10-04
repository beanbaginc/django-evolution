import unittest

from signature import tests as signature_tests
from add_field import tests as add_field_tests
from delete_field import tests as delete_field_tests
from rename_field import tests as rename_field_tests
from sql_mutation import tests as sql_mutation_tests

# Define doctests
__test__ = {
    'signature': signature_tests,
    'add_field': add_field_tests,
    'delete_field': delete_field_tests,
    'rename_field': rename_field_tests,
    'sql_mutation': sql_mutation_tests,
}

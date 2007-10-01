from django_evolution.mutations import *
from regressiontests.schema_evolution.models import *

# For the first migration, perform the following mutations in order.

# In terms of the test, this is merely a stub and won't be actually invoked.
# The test will insert the appropriate migrations as they are tested.
MUTATIONS = [ DeleteField(Person,'surname')]

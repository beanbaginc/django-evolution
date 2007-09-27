from django.contrib.evolution.mutation import *
from test_app.models import *

MUTATIONS = [ RenameField(Person,'name','first_name'),
	          DeleteField(Person,'today'),]

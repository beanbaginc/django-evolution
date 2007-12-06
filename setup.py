from distutils.core import setup

setup(
    name='django_evolution',
    description='An implementation of schema evolution for the Django web framework.',
    author='Ben Khoo',
    author_email='khoobks@westnet.com.au',
    url='http://code.google.com/p/django-evolution/',
    packages=[
        'django_evolution',
        'django_evolution.db',
        'django_evolution.management',
        'django_evolution.management.commands',
        'django_evolution.tests',
        'django_evolution.tests.db',
    ],
)

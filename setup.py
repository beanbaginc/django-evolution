#!/usr/bin/env python
#
# Setup script for Django Evolution

from setuptools import setup, find_packages
from setuptools.command.test import test

from django_evolution import get_package_version


def run_tests(*args):
    import os
    os.system('tests/runtests.py')

test.run_tests = run_tests


# Build the package
setup(
    name='django_evolution',
    version=get_package_version(),
    description='A database schema evolution tool for the Django web framework.',
    url='https://github.com/beanbaginc/django-evolution',
    author='Ben Khoo',
    author_email='khoobks@westnet.com.au',
    maintainer='Christian Hammond',
    maintainer_email='christian@beanbaginc.com',
    packages=find_packages(exclude=['tests']),
    install_requires=[
        'Django>=1.4.10',
    ],
    include_package_data=True,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)

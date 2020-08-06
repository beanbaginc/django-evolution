#!/usr/bin/env python
#
# Setup script for Django Evolution

from setuptools import setup, find_packages
from setuptools.command.test import test

from django_evolution import get_package_version, VERSION


def run_tests(*args):
    import os
    os.system('tests/runtests.py')

test.run_tests = run_tests


PACKAGE_NAME = 'django_evolution'

download_url = (
    'https://downloads.reviewboard.org/releases/django-evolution/%s.%s/' %
    (VERSION[0], VERSION[1]))


with open('README.rst', 'r') as fp:
    long_description = fp.read()


# Build the package
setup(
    name=PACKAGE_NAME,
    version=get_package_version(),
    license='BSD',
    description=('A database schema evolution tool for the Django web '
                 'framework.'),
    long_description=long_description,
    long_description_content_type='text/x-rst',
    url='https://github.com/beanbaginc/django-evolution',
    author='Ben Khoo',
    author_email='khoobks@westnet.com.au',
    maintainer='Beanbag, Inc.',
    maintainer_email='reviewboard@googlegroups.com',
    download_url=download_url,
    packages=find_packages(exclude=['tests']),
    install_requires=[
        'Django>=1.6,<3.1.999',
        'python2-secrets; python_version == "3.5"',
    ],
    include_package_data=True,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Framework :: Django',
        'Framework :: Django :: 1.6',
        'Framework :: Django :: 1.7',
        'Framework :: Django :: 1.8',
        'Framework :: Django :: 1.9',
        'Framework :: Django :: 1.10',
        'Framework :: Django :: 1.11',
        'Framework :: Django :: 2.1',
        'Framework :: Django :: 2.2',
        'Framework :: Django :: 3.0',
        'Framework :: Django :: 3.1',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)

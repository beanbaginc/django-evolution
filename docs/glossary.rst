.. _glossary:


========
Glossary
========

.. glossary::

   Evolution Label
       The name of a particular evolution for an app. These must be unique
       within an app, but do not have to be unique within a project.

   Legacy App Label
   Legacy App Labels
       The form of app label used in Django 1.6 and earlier. Legacy app labels
       are generated solely from the app's module name.

   Migrations
       Django 1.7+'s built-in method of managing changes to the database
       schema. See the `migrations documentation`_.

   Modern App Label
   Modern App Labels
       The form of app label used in Django 1.7 and later. Modern app labels
       default to being generated from the app's module name, but can be
       customized.

   Project Signature
   Project Signatures
       A stored representation of all the apps and models in your project.
       This is stored in the ``django_project_version`` table, and is a
       critical part in determining how the database has evolved and what
       changes need to be made.

       In Django Evolution 2.0 and higher, this is stored as JSON data. In
       prior versions, this was stored as Pickle protocol 0 data.


.. _migrations documentation:
   https://docs.djangoproject.com/en/1.11/topics/migrations/

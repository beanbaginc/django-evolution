.. This is here first to ensure priority over the FAQ toctree in the page.
.. toctree::
   :hidden:

   how-does-it-work
   faq
   installation
   writing-evolutions
   mutations
   commands/index
   glossary
   releasenotes/index


==============================
Django Evolution Documentation
==============================

Django Evolution is a database schema migration tool for projects using the
Django_ web framework. Its job is to help projects make changes to a
database's schema -- the structure of the tables and columns and indexes --
in the fastest way possible (incurring minimum downtime) and in a way that
works across all Django-supported databases.

This is very similar in concept to the built-in :term:`migrations` support in
Django 1.7 and higher. Django Evolution predates both Django's own migrations,
and works alongside it to transition databases taking advantage of the
strengths of both migrations and evolutions.

While most will be fine with :term:`migrations`, there's a couple reasons why
you might find Django Evolution a worthwhile addition to your project:

1. You're still stuck on Django 1.6 or earlier and need to make changes to
   your database.

   Django 1.6 is the last version without built-in support for migrations,
   and there are still codebases out there using it. Django Evolution can
   help keep upgrades manageable, and make it easier to transition all or
   part of your codebase to migrations when you finally upgrade.

2. You're distributing a self-installable web application, possibly used in
   large enterprises, where you have no control over when people are going to
   upgrade.

   Django's migrations assume some level of planning around when changes are
   made to the schema and when they're applied to a database. The more changes
   you make, and the more versions in-between what the user is running and
   what they upgrade to, the longer the upgrade time.

   If a customer is in control of when they upgrade, they might end up with
   *years* of migrations that need to be applied.

   Migrations apply one-by-one, possibly triggering the rebuild of a
   table many times during an upgrade. Django Evolution, on the other hand,
   can apply years worth of evolutions at once, optimized to perform as few
   table changes as possible. This can take days, hours or even *seconds* off
   the upgrade time.

Django Evolution officially supports Django 1.6 through 3.1.


Questions So Far?
=================

* :doc:`how-does-it-work`

.. toctree::
   :maxdepth: 2

   faq


Let's Get Started
=================

* :doc:`Install Django Evolution <installation>`
* :doc:`Writing Your First Evolution <writing-evolutions>`
* :doc:`Exploring App and Model Mutations <mutations>`
* :doc:`Apply evolutions with \`evolve --execute\` <commands/evolve>`


Reference
=========

.. toctree::
   :maxdepth: 2

   commands/index


.. toctree::
   :maxdepth: 1

   versioning
   coderef/index


.. toctree::
   :maxdepth: 3

   releasenotes/index


.. _Django: https://www.djangoproject.com/

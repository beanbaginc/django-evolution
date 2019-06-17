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

Django Evolution officially supports Django 1.6 through 1.11, with support
for 2.0 in the works.


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

   coderef/index


.. _Django: https://www.djangoproject.com/

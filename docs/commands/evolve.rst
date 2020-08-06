.. program:: evolve
.. _command-evolve:

======
evolve
======

The :command:`evolve` command is responsible for setting up databases and
applying any evolutions or :term:`migrations`.

This is a replacement for both the :command:`syncdb` and :command:`migrate`
commands in Django. Running either of this will wrap :command:`evolve` (though
not all of the command's arguments will be supported when Django Evolution is
enabled).


Creating/Updating Databases
===========================

To construct a new database or apply updates, you will generally just run::

   $ ./manage.py evolve --execute

This is the most common usage for :command:`evolve`. It will create any
missing models and apply any unapplied evolutions or :term:`migrations`.

.. versionchanged:: 2.0
   :command:`evolve` now replaces both :command:`syncdb` and
   :command:`migrate`. In previous versions, it had to be run after
   :command:`syncdb`.


Generating Hinted Evolutions
============================

When making changes to a model, it helps to see how the evolution should look
before writing it. Sometimes the evolution will be usable as-is, but sometimes
you'll need to tweak it first.

To generate a hinted evolution, run::

   $ ./manage.py evolve --hint

Hinted evolutions can be automatically written by using :option:`--write`,
saving you a little bit of work::

   $ ./manage.py evolve --hint --write my_new_evolution

This will take any app with a hinted evolution and write a
:file:`{appdir}/evolutions/my_new_evolution.py` file. You will still need to
add your new evolution to the ``SEQUENCE`` list in
:file:`{appdir}/evolutions/__init__.py`.

If you only want to write hints for a specific app, pass the app labels on the
command line, like so::

   $ ./manage.py evolve --hint --write my_new_evolution my_app


Arguments
=========

.. option:: <APP_LABEL...>

   Zero or more specific app labels to evolve. If provided, only these apps
   will have evolutions or :term:`migrations` applied. If not provided, all
   apps will be considered for evolution.

.. option:: --database <DATABASE>

   The name of the configured database to perform the evolution against.

.. option:: --hint

   Display sample evolutions that fulfill any database changes for apps and
   models managed by evolutions. This won't include any apps or models
   managed by :term:`migrations`.

.. option:: --noinput

   Perform evolutions automatically without any input.

.. option:: --purge

   Remove information on any non-existent applications from the stored
   project signature. This won't remove the models themselves. For that,
   see :ref:`mutation-delete-model` or :ref:`mutation-delete-application`.

.. option:: --sql

   Display the generated SQL that would be run if applying evolutions.
   This won't include any apps or models managed by :term:`migrations`.

.. option:: -w <EVOLUTION_NAME>, --write <EVOLUTION_NAME>

   Write any hinted evolutions to a file named
   :file:`{appdir}/evolutions/{EVOLUTION_NAME}`. This will *not* include the
   evolution in :file:`{appdir}/evolutions/__init__.py`.

.. option:: -x, --execute

   Execute the evolution process, applying any evolutions and
   :term:`migrations` to the database.

   .. warning::

      This can be used in combination with :option:`--hint` to apply hinted
      evolutions, but this is generally a **bad idea**, as the execution is
      not properly repeatable or trackable.

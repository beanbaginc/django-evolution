.. program:: wipe-evolution
.. _command-wipe-evolution:

==============
wipe-evolution
==============

The :command:`wipe-evolution` command is used to remove evolutions from the
list of applied evolutions.

This is really only useful if you're working to recover from a bad state where
you've undone the changes made by an evolution and need to re-apply it. It
should never be used under normal use, especially on a production database.

By default, this command will confirm before wiping the evolution from the
history. You can use :option:`--noinput` to avoid the confirmation step.

To see the list of evolutions that can be wiped, run
:command:`list-evolutions`.


Example
=======

::

    $ ./manage.py wipe-evolution --app-label my_app change_name_max_length


Arguments
=========

.. option:: EVOLUTION_LABEL ...

   One or more specific evolution labels to remove from the database. If the
   same evolution names exist for multiple apps, they'll all be removed. To
   isolate them to a specific app, use :option:`--app-label`.

.. option:: --app-label <APP_LABEL>

   An app label to limit evolution labels to. Only evolutions on this app will
   be wiped.

.. option:: --noinput

   Perform the wiping procedure automatically without any input.

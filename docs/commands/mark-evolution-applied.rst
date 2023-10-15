.. program:: mark-evolution-applied
.. _command-mark-evolution-applied:

======================
mark-evolution-applied
======================

The :command:`mark-evolution-applied` command is used to mark evolutions as
already applied in the database.

This is really only useful if you're working to recover from a bad state where
you've undone the changes made by an evolution and need to re-apply it. It
should never be used under normal use, especially on a production database.

By default, this command will confirm before marking the evolution as applied.
You can use :option:`--noinput` to avoid the confirmation step.


Example
=======

.. code-block:: console

    $ ./manage.py mark-evolution-applied --app-label my_app \
          change_name_max_length


Arguments
=========

.. option:: EVOLUTION_LABEL ...

   One or more specific evolution labels to mark as applied. This is required
   if :option:`--all` isn't specified.

.. option:: --all

   Mark all unapplied evolutions as applied.

.. option:: --app-label <APP_LABEL>

   An app label the evolutions apply to.

.. option:: --noinput

   Mark as applied without prompting for confirmation.

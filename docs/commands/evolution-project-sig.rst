.. program:: evolution-project-sig
.. _command-evolution-project-sig:

======================
evolution-project-sig
======================

The :command:`evolution-project-sig` command is used to list, show, and delete
stored project signatures.

This is really only useful if you're working to recover from a bad state where
you've undone the changes made by an evolution and need to re-apply it. It
should never be used under normal use, especially on a production database.

By default, this command will confirm before making any changes to the
database. You can use :option:`--noinput` to avoid the confirmation step.


Example
=======

To list project signatures:

.. code-block:: console

    $ ./manage.py evolution-project-sig --list

To show the latest project signature:

.. code-block:: console

    $ ./manage.py evolution-project-sig --show

To show a specific project signature:

.. code-block:: console

    $ ./manage.py evolution-project-sig --show --id <ID>

To delete a project signature:

.. code-block:: console

    $ ./manage.py evolution-project-sig --delete --id <ID>


Arguments
=========

.. option:: ---delete

   Delete a project signature.

.. option:: --list

   List project signatures and their associated evolutions.

.. option:: --show

   Show the current project signature, or an older one if using
   :option:`--id`.

.. option:: --id

   Specify the ID of a project signature.

.. option:: --noinput

   Delete without prompting for confirmation.

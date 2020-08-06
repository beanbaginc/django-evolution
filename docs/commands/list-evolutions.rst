.. program:: list-evolutions
.. _command-list-evolutions:

===============
list-evolutions
===============

The :command:`list-evolutions` command lists all the evolutions that have so
far been applied to the database. It can be useful for debugging, or
determining if a specific evolution has yet been applied.


Example
=======

::

   $ ./manage.py list-evolutions my_app
   Applied evolutions for 'my_app':
       add_special_fields
       update_app_label
       change_name_max_length


Arguments
=========

.. option:: <APP_LABEL...>

   Zero or more specific app labels to list. If provided, only evolutions on
   these apps will be shown.

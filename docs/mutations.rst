.. _mutations:

=======================
App and Model Mutations
=======================

Evolutions are composed of one or more mutations, which mutate the state of
the app or models. There are several mutations included with Django Evolution,
which we'll take a look at here.


.. _mutations-fields:

Field Mutations
===============


.. _mutation-add-field:

AddField
--------

``AddField`` is used to add new fields to a table. It takes the following
parameters:

.. py:class:: AddField(model_name, field_name, field_type, initial=None, **field_attrs)

   :param str model_name:
       The name of the model the field was added to.

   :param str field_name:
       The name of the new field.

   :param type field_type:
       The field class.

   :param initial:
       The initial value to set for the field. Each row in the table will have
       this value set once the field is added.  It's required if the field is
       non-null.

   :param dict field_attrs:
       Attributes to pass to the field constructor. Only those that impact the
       schema of the table are considered (for instance, ``null=...`` or
       ``max_length=...``, but not ``help_text=...``.

For example:

.. code-block:: python

   from django.db import models
   from django_evolution.mutations import AddField


   MUTATIONS = [
       AddField('Book', 'publish_date', models.DateTimeField, null=True),
   ]


.. _mutation-change-field:

ChangeField
-----------

``ChangeField`` can make changes to existing fields, altering the attributes
(for instance, increasing the maximum length of a ``CharField``).

.. note::
   This cannot be used to change the field type.

It takes the following parameters:

.. py:class:: ChangeField(model_name, field_name, initial=None, **field_attrs)

   :param str model_name:
       The name of the model containing the field.

   :param str field_name:
       The name of the field to change.

   :param initial:
       The new initial value to set for the field. If the field previously
       allowed null values, but ``null=False`` is being passed, then this will
       update all existing rows in the table to have this initial value.

   :param dict field_attrs:
       The field attributes to change. Only those that impact the schema of
       the table are considered (for instance, ``null=...`` or
       ``max_length=...``, but not ``help_text=...``.


For example:

.. code-block:: python

   from django.db import models
   from django_evolution.mutations import ChangeField


   MUTATIONS = [
       ChangeField('Book', 'name', max_length=100, null=False),
   ]


.. _mutation-delete-field:

DeleteField
-----------

``DeleteField`` will delete a field from the table, erasing its data from all
rows. It takes the following parameters:

.. py:class:: DeleteField(model_name, field_name)

   :param str model_name:
       The name of the model containing the field to delete.

   :param str field_name:
       The name of the field to delete.

For example:

.. code-block:: python

   from django.db import models
   from django_evolution.mutations import ChangeField


   MUTATIONS = [
       ChangeField('Book', 'name', max_length=100, null=False),
   ]


.. _mutation-rename-field:

RenameField
-----------

``RenameField`` will rename a field in the table, preserving all stored data.
It can also set an explicit column name (in case the name is only changing in
the model) or a :py:class:`~django.db.models.ManyToManyField` table name.

If working with a :py:class:`~django.db.models.ManyToManyField`, then the
parent table won't actually have a real column backing it. Instead, the
relationships are all maintained using the "through" table created by the
field. In this case, the ``db_column`` value will be ignored, but ``db_table``
can be set.

It takes the following parameters:

.. py:class:: RenameField(model_name, old_field_name, new_field_name, db_column=None, db_table=None)

   :param str model_name:
       The name of the model containing the field to delete.

   :param str old_field_name:
       The old name of the field on the model.

   :param str new_field_name:
       The new name of the field on the model.

   :param str db_column:
       The explicit name of the column on the table to use. This may be the
       original column name, if the name is only being changed on the model
       (which means no database changes may be made).

   :param str db_table:
       The explicit name of the "through" table to use for a
       :py:class:`~django.db.models.ManyToManyField`. If changed, then that
       table will be renamed. This is ignored for any other types of fields.

       If the table name hasn't actually changed, then this may not make any
       changes to the database.

For example:

.. code-block:: python

   from django_evolution.mutations import RenameField


   MUTATIONS = [
       RenameField('Book', 'isbn_number', 'isbn', column_name='isbn_number'),
       RenameField('Book', 'critics', 'reviewers',
                   db_table='book_critics')
   ]


.. _mutations-models:

Model Mutators
==============


.. _mutation-change-meta:

ChangeMeta
----------

``ChangeMeta`` can change certain bits of metadata about a model. For example,
the indexes or unique-together constraints. It takes the following parameters:

.. py:class:: ChangeMeta(model_name, prop_name, new_value)

   :param str model_name:
       The name of the model containing the field to delete.

   :param str prop_name:
       The name of the property to change, as documented below.

   :param new_value:
       The new value for the property.

The properties that can be changed depend on the version of Django. They
include:

``index_together``:
    Groups of fields that should be indexed together in the database.

    This is represented by a list of tuples, each of which groups together
    multiple field names that should be indexed together in the database.

    ``index_together`` support requires Django 1.5 or higher. The last
    versions of Django Evolution to support Django 1.5 was the 0.7.x series.

``indexes``:
    Explicit indexes to create for the model, optionally grouping multiple
    fields together and optionally naming the index.

    This is represented by a list of dictionaries, each of which contain a
    ``fields`` key and an optional ``name`` key. Both of these correspond to
    the matching fields in Django's :py:class:`~django.db.models.Index` class.

    ``indexes`` support requires Django 1.11 or higher.

``unique_together``:
    Groups of fields that together form a unique constraint. Rows in the
    database cannot repeat the same values for those groups of fields.

    This is represented by a list of tuples, each of which groups together
    multiple field names that should be unique together in the database.

    ``unique_together`` support is available in all supported versions of
    Django.


For example:

.. code-block:: python

   from django_evolution.mutations import ChangeMeta


   MUTATIONS = [
       ChangeMeta('Book', 'index_together', [('name', 'author')]),
   ]


.. versionchanged:: 2.0
   Added support for ``indexes``.


.. _mutation-delete-model:

DeleteModel
-----------

``DeleteModel`` removes a model from the database.  It will also remove any
"through" models for any of its :py:class:`ManyToManyFields
<django.db.models.ManyToManyField>`. It takes the following parameters:

.. py:class:: DeleteModel(model_name)

   :param str model_name:
       The name of the model to delete.

For example:

.. code-block:: python

   from django_evolution.mutations import DeleteModel


   MUTATIONS = [
       DeleteModel('Book'),
   ]


.. _mutation-rename-model:

RenameModel
-----------

``RenameModel`` will rename a model and update all relations pointing to that
model. It requires an explicit underlying table name, which can be set to the
original table name if only the Python-side model name is changing. It takes
the following parameters:

.. py:class:: RenameModel(old_model_name, new_model_name, db_table)

   :param str old_model_name:
       The old name of the model.

   :param str new_model_name:
       The new name of the model.

   :param str db_table:
       The explicit name of the underlying table.

For example:

.. code-block:: python

   from django_evolution.mutations import RenameModel


   MUTATIONS = [
       RenameModel('Critic', 'Reviewer', db_table='books_reviewer'),
   ]


.. _mutations-apps:

App Mutators
============


.. _mutation-delete-application:

DeleteApplication
-----------------

``DeleteApplication`` will remove all the models for an app from the database,
erasing all associated data. This mutation takes no parameters.

.. note::
   Make sure that any relation fields from other models to this app's models
   have been removed before deleting an app.

   In many cases, you may just want to remove the app from your project's
   :django:setting:`INSTALLED_APPS`, and leave the data alone.

For example:

.. code-block:: python

   from django_evolution.mutations import DeleteApplication


   MUTATIONS = [
       DeleteApplication(),
   ]


.. _mutation-move-to-django-migrations:

MoveToDjangoMigrations
----------------------

``MoveToDjangoMigrations`` will tell Django Evolution that any future changes
to the app or its models should be handled by Django's :term:`migrations`
instead evolutions. Any unapplied evolutions will be applied before applying
any migrations.

This is a one-way operation. Once an app moves from evolutions to migrations,
it cannot move back.

Since an app may have had both evolutions and migrations defined in the tree
(in order to work with both systems), this takes a ``mark_applied=`` parameter
that lists the migrations that should be considered applied by the time this
mutation is run. Those migrations will be recorded as applied and skipped.

.. py:class:: MoveToDjangoMigrations(mark_applied=['0001_initial'])

   :param list mark_applied:
       The list of migrations that should be considered applied when running
       this mutation. This defaults to the ``0001_initial`` migration.

For example:

.. code-block:: python

   from django_evolution.mutations import MoveToDjangoMigrations


   MUTATIONS = [
       MoveToDjangoMigrations(mark_applied=['0001_initial',
                                            '0002_book_add_isbn']),
   ]

.. versionadded:: 2.0


.. _mutation-rename-app-label:

RenameAppLabel
--------------

``RenameAppLabel`` will rename the stored app label for the app, updating
all references made in other models. It won't change indexes or any database
state, however.

Django 1.7 moved to an improved concept of app labels that could be customized
and were guaranteed to be unique within a project (we'll call these
:term:`modern app labels`). Django 1.6 and earlier generated app labels based
on the app's module name (:term:`legacy app labels`).

Because of this, older stored :term:`project signatures` may have grouped
together models from two different apps (both with the same app labels)
together. Django Evolution will *try* to untangle this, but in complicated
cases, you may need to supply a list of model names for the app (current and
possibly older ones that have been removed). Whether you need to do this is
entirely dependent on the structure of your project. Test it in your upgrades.

This takes the following parameters:

.. py:class:: RenameAppLabel(old_app_label, new_app_label, legacy_app_label=None, model_names=None)

   :param str old_app_label:
       The old app label that's being renamed.

   :param str new_app_label:
       The new modern app label to rename to.

   :param str legacy_app_label:
       The legacy app label for the new app name. This provides compatibility
       with older versions of Django and helps with transition apps and
       models.

   :param list model_names:
       The list of model names to move out of the old signature and into the
       new one.

For example:

.. code-block:: python

   from django_evolution.mutations import RenameAppLabel


   MUTATIONS = [
       RenameAppLabel('admin', 'my_admin', legacy_app_label='admin',
                      model_names=['Report', 'Config']),
   ]

.. versionadded:: 2.0


.. _mutations-other:

Other Mutators
==============


.. _mutation-sql-mutation:

SQLMutation
-----------

``SQLMutation`` is an advanced mutation used to make arbitrary changes to a
database and to the stored project signature. It may be used to make changes
that cannot be made by other mutators, such as altering tables not managed by
Django, changing a table engine, making metadata changes to the table or
database, or modifying the content of rows.

SQL from this mutation cannot be optimized alongside other mutations.

This takes the following parameters:

.. py:class:: SQLMutation(tag, sql, update_func=None)

   :param str tag:
       A unique identifier for this SQL mutation within the app.

   :param list/str sql:
       A list of SQL statements, or a single SQL statement as a string, to
       execute. Note that this will be database-dependent.

   :param callable update_func:
       A function to call to perform additional operations or update the
       :term:`project signature`.

.. note::
   There's some caveats with providing an ``update_func``.

   Django Evolution 2.0 introduced a new form for this function that takes in
   a :py:class:`django_evolution.mutations.Simulation` object, which can be
   used to access and modify the stored :term:`project signature`. This is
   safe to use (well, relatively -- try not to blow anything up).

   Prior versions supported a function that took two arguments: The app label
   of the app that's being evolved, and a serialized dictionary representing
   the project signature.

   If using the legacy style, it's *possible* that you can mess up the
   signature data, since we have to serialize to an older version of the
   signature and then load from that. Older versions of the signature don't
   support all the data that newer versions do, so how well this works is
   really determined by the types of evolutions that are going to be run.

   We **strongly** recommend updating *any* ``SQLMutation`` calls to use the
   new-style function format, for safety and future compatibility.


For example:

.. code-block:: python

   from django_evolution.mutations import SQLMutation


   def _update_signature(simulation):
       pass


   MUTATIONS = [
       SQLMutation('set_innodb_engine',
                   'ALTER TABLE my_table ENGINE = MYISAM;',
                   update_func=_update_signature),
   ]


.. versionchanged:: 2.0
   Added the new-style ``update_func``.

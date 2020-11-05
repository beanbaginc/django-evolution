==================
Writing Evolutions
==================

Evolution files describe a set of changes made to an app or its models. These
are Python files that live in the :file:`{appdir}/evolutions/` directory.
The name of the file (minus the ``.py`` extension) is called an
:term:`evolution label`, and can be whatever you want, so long as it's unique
for the app. These files look something like:

.. code-block:: python
   :caption: myapp/evolutions/my_evolution.py

   from __future__ import unicode_literals

   from django_evolution.mutations import AddField


   MUTATIONS = [
       AddField('MyModel', 'my_field', models.CharField, max_length=100,
                null=True),
   ]


Evolution files can make use of any supported :ref:`mutations` (classes like
``AddField`` above) to describe the changes made to your app or models.

Once you've written an evolution file, you'll need to place its label in the
app's :file:`{appdir}/evolutions/__init__.py` in a list called ``SEQUENCE``.
This specifies the order in which evolutions should be processed. These look
something like:

.. code-block:: python
   :caption: myapp/evolutions/__init__.py

   from __future__ import unicode_literals

   SEQUENCE = [
       'my_evolution',
   ]


Example
=======

Let's go through an example, starting with a model.

.. code-block:: python
   :caption: blogs/models.py

   class Author(models.Model):
       name = models.CharField(max_length=50)
       email = models.EmailField()
       date_of_birth = models.DateField()


   class Entry(models.Model):
       headline = models.CharField(max_length=255)
       body_text = models.TextField()
       pub_date = models.DateTimeField()
       author = models.ForeignKey(Author)


At this point, we'll assume that the project has been previously synced to the
database using something like ``./manage.py syncdb`` or ``./manage.py migrate
--run-syncdb``. We will also assume that it does *not* make use of
:term:`migrations`.


Modifying Our Model
-------------------

Perhaps we decide we don't actually need the birthdate of the author. It's
just extra data we're doing nothing with, and increases the maintenance
burden. Let's get rid of it.


.. code-block:: diff

    class Author(models.Model):
        name = models.CharField(max_length=50)
        email = models.EmailField()
   -    date_of_birth = models.DateField()

The field is gone, but it's still in the database. We need to generate an
evolution to get rid of it.

We can get a good idea of what this should look like by running::

    $ ./manage.py evolve --hint


Which gives us::

    #----- Evolution for blogs
    from __future__ import unicode_literals

    from django_evolution.mutations import DeleteField


    MUTATIONS = [
        DeleteField('Author', 'date_of_birth'),
    ]
    #----------------------

    Trial upgrade successful!


As you can see, we got some output showing us what the evolution file might
look like to delete this field. We're also told that this worked -- this
evolution was enough to update the database based on our changes. If we had
something more complex (like adding a non-null field, requiring some sort of
initial value), then we'd be told we still have changes to make.

Let's dump this sample file in
:file:`blogs/evolutions/remove_date_of_birth.py`:

.. code-block:: python
   :caption: blogs/evolutions/remove_date_of_birth.py

   from __future__ import unicode_literals

   from django_evolution.mutations import DeleteField


   MUTATIONS = [
       DeleteField('Author', 'date_of_birth'),
   ]


(Alternatively, we could have run ``./manage.py evolve -w
remove_date_of_birth``, which would create this file for us, but let's start
off this way.)

Now we need to tell Django Evolution we want this in our evolution sequence:

.. code-block:: python
   :caption: blogs/evolutions/remove_date_of_birth.py

   from __future__ import unicode_literals

   SEQUENCE = [
       'remove_date_of_birth',
   ]


We're done with the hard work! Time to apply the evolution:


.. code-block::

   $ ./manage.py evolve --execute

   You have requested a database upgrade. This will alter tables and data
   currently in the "default" database, and may result in IRREVERSABLE
   DATA LOSS. Upgrades should be *thoroughly* reviewed and tested prior
   to execution.

   MAKE A BACKUP OF YOUR DATABASE BEFORE YOU CONTINUE!

   Are you sure you want to execute the database upgrade?

   Type "yes" to continue, or "no" to cancel: yes

   This may take a while. Please be patient, and DO NOT cancel the
   upgrade!

   Applying database evolution for blogs...
   The database upgrade was successful!


Tada! Now if you look at the columns for your ``blogs_author`` table, you'll
find that ``date_of_birth`` is gone.

You can make changes to your models as often as you need to. Add and delete
the same field a dozen times across dozens of evolutions, if you like.
Evolutions are automatically optimized before applied, resulting in the
smallest set of changes needed to get your database updated.


.. _evolution-dependencies:

Adding Dependencies
-------------------

.. versionadded:: 2.1

Both individual evolution modules and the main
``myapp/evolutions/__init__.py`` module can define other evolutions or
migrations that must be applied before or after the individual evolution or
app as a whole.

This is done by adding any of the following to the appropriate module:

``AFTER_EVOLUTIONS``:
    A list of specific evolutions (tuples in the form of
    ``(app_label, evolution_label)``) or app labels (a single string) that
    must be applied before this evolution can be applied.

``BEFORE_EVOLUTIONS``:
    A list of specific evolutions (tuples in the form of
    ``(app_label, evolution_label)``) or app labels (a single string) that
    must be applied sometime after this evolution is applied.

``AFTER_MIGRATIONS``:
    A list of migration targets (tuples in the form of
    ``(app_label, migration_name)`` that must be applied before this evolution
    can be applied.

``BEFORE_MIGRATIONS``:
    A list of migration targets (tuples in the form of
    ``(app_label, migration_name)`` that must be applied sometime after this
    evolution is applied.

Django Evolution will apply the evolutions and migrations in the right order
based on any dependencies.

This is important to set if you have evolutions that a migration may depend on
(e.g., a swappable model that the migration requires), or if your evolutions
are being applied in the wrong order (often only a problem if there are
evolutions depending on migrations).

.. note:: It's up to you to decide where to put these.

   You may want to define this as its own empty ``initial.py`` evolution
   at the beginning of the ``SEQUENCE`` list, or to a more specific
   ``evolution`` within.


So, let's look at an example:

.. code-block:: python
   :caption: blogs/evolutions/add_my_field.py

   from __future__ import unicode_literals

   from django_evolution.mutations import ...


   BEFORE_EVOLUTIONS = [
       'blog_exporter',
       ('myapi', 'add_blog_fields'),
   ]

   AFTER_MIGRATIONS = [
       ('fancy_text', '0001_initial'),
   ]

   MUTATIONS = [
       ...
   ]


This will ensure this evolution is applied before both the ``blog_exporter``
app's evolutions/models and the ``myapi`` app's ``add_blog_fields`` evolution.
At the same time, it'll also ensure that it will be applied only after the
``fancy_text`` app's ``0001_initial`` migration has been applied.

Similarly, these can be added to the top-level ``evolutions/__init__.py`` file
for an app:

.. code-block:: python
   :caption: blogs/evolutions/__init__.py

   from __future__ import unicode_literals


   BEFORE_EVOLUTIONS = [
       'blog_exporter',
       ('myapi', 'add_blog_fields'),
   ]

   AFTER_MIGRATIONS = [
       ('fancy_text', '0001_initial'),
   ]

   SEQUENCE = [
       'add_my_field',
   ]

This is handy if you need to be sure that this module's evolutions or model
creations always happen before or after that of another module, no matter
which models may exist or which evolutions may have already been applied.


.. hint::

   Don't add dependencies if you don't need to. Django Evolution will try to
   apply the ordering in the correct way. Use dependencies when it gets it
   wrong.

   Make sure you test not only upgrades but the creation of brand-new
   databases, to make sure your dependencies are correct in both cases.


MoveToDjangoMigrations
~~~~~~~~~~~~~~~~~~~~~~

If an evolution uses the
:py:class:`~django_evolution.mutations.MoveToDjangoMigrations` mutation,
dependencies will automatically be created to ensure that your evolution is
applied in the correct order relative to any new migrations in that app.

That means that this:

.. code-block:: python

   MUTATIONS = [
       MoveToDjangoMigrations(mark_applied=['0001_initial'])
   ]


implies:

.. code-block:: python

   AFTER_MIGRATIONS = [
       ('myapp', '0001_initial'),
   ]

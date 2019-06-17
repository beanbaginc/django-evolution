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

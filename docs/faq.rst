==========================
Frequently Asked Questions
==========================

Who maintains Django Evolution?
===============================

Originally, Django Evolution was built by two guys in Perth, Australia: `Ben
Khoo`_ and `Russell Keith-Magee`_ (a core developer on Django).

Since then, Django Evolution has been taken over by `Beanbag, Inc.`_. We have
a vested interest in keeping this alive, well-maintained, and open source for
`Review Board`_ and other products.

.. _Beanbag, Inc.: https://www.beanbaginc.com/
.. _Ben Khoo: mailto:khoobks@westnet.com.au
.. _Review Board: https://www.reviewboard.org/
.. _Russell Keith-Magee: mailto:russell@keith-magee.com


Where do I go for support?
==========================

We have a really old `mailing list`_ over at Google Groups, where you can ask
questions. Truthfully, this group is basically empty these days, but you can
still ask there and we'll answer!

We also provide commercial support. You can `reach out to us`_ if you're using
Django Evolution in production and want the assurance of someone you can reach
24/7 if something goes wrong.

.. _mailing list: http://groups.google.com/group/django-evolution
.. _reach out to us: mailto:sales@beanbaginc.com


What about bug reports?
=======================

You can report bugs on our `bug tracker`_, hosted on Splat_.

When you file a bug, please be as thorough as possible. Ideally, we'd like to
see the contents of your ``django_project_version`` and ``django_evolution``
tables before and after the upgrade, along with any evolution files, models,
and error logs.


.. _bug tracker: https://hellosplat.com/s/beanbag/django-evolution/
.. _Splat: https://www.hellosplat.com/


How do I contribute patches/pull requests?
==========================================

We'd love to work with you on your contributions to Django Evolution! It'll
make our lives easier, for sure :)

While we don't work with pull requests, we do accept patches on
reviews.reviewboard.org_, our `Review Board`_ server. You can get started by
cloning our `GitHub repository`_, and `install RBTools`_ (the Review Board command
line tools).

To post new changes from your feature branch for review, run::

    $ rbt post

To update an existing review request::

    $ rbt post -u

See the `RBTools documentation`_ for more usage info.


.. _reviews.reviewboard.org: https://reviews.reviewboard.org/
.. _GitHub repository: https://github.com/beanbaginc/django-evolution
.. _install RBTools: https://www.reviewboard.org/downloads/rbtools/
.. _RBTools documentation: https://www.reviewboard.org/docs/rbtools/


Why evolutions and not migrations?
==================================

While most new projects would opt for Django's own :term:`migrations`, there
are a few advantages to using evolutions:

1. Evolutions are faster to apply than migrations when upgrading between
   arbitrary versions of the schema.

   Migrations are applied one at a time. If you have 10 migrations modifying
   one table, then you'll trigger a table rebuild 10 times, which is slow --
   particularly if there's a lot of data in that table.

   Evolutions going through an optimization process before they're applied,
   determining the smallest amount of changes needed. 10 evolutions for a
   table will generally only trigger a single table rebuild.

   When you fully own the databases you're upgrading, this may not matter, as
   you're probably applying new migrations as you write them. However, if
   you are distributing self-installed web services (such as `Review Board`_),
   administrators may not upgrade often. Evolutions help keep these large
   upgrades from taking forever.

2. There's a wide range of Django support.

   If you are still maintaining legacy applications on Django 1.6, it may be
   hard to transition to newer versions. By switching to Django Evolution,
   there's a transition path. You can use evolutions for the apps you control
   without conflicting with migrations, and begin the upgrade path to modern
   versions of Django.

   At any time, you can easily switch some or all of your apps from evolutions
   to migrations, and Django Evolution will take care of it automatically.

3. Django Evolution is easier for some development processes.

   During development, you may make numerous changes to your database,
   necessitating schema changes that you wouldn't want to apply in production.
   With migrations, you'd need to squash those development-only migration
   files, which doesn't play as well if some beta users have only a subset of
   those migrations applied.


Can I switch apps from evolutions to migrations?
================================================

Yes, you can! The :ref:`mutation-move-to-django-migrations` mutation will
instruct Django Evolution to use :term:`migrations` instead of evolutions for
any future changes. Before it hands your app off entirely, it will apply any
unapplied evolutions, ensuring a sane starting point for your new migrations.


Can I switch apps from migrations to evolutions?
================================================

No, it's one way for now. We might add this if anyone wants it in the future.
For now, we assume that people using migrations are satisfied with that, and
aren't looking to move to evolutions.


Why do my syncdb/migrate commands act differently?
==================================================

Starting in Django Evolution 2.0, the :ref:`command-evolve` command has
taken over all responsibilities for creating and updating the database,
replacing ``syncdb`` and ``migrate``.

For compatibility, those two commands have been replaced, wrapping
:ref:`command-evolve` instead. Some functionality had to be stripped away
from the original commands, though.

Our ``syncdb`` and ``migrate`` commands don't support loading ``initial_data``
fixtures. This feature was deprecated in Django 1.7 and removed in 1.9, and
keeping support between Django versions is tricky. We've opted not to include
it (at least for now).

Our ``migrate`` command doesn't support specifying explicit migration names to
apply, or using ``--fake`` to pretend migrations were applied.

It's possible we'll add compatibility in the future, but only if demand is
strong.

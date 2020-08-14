================
Django Evolution
================

Django Evolution is an add-on to the Django_ web framework that helps manage
changes to the database schema.

"But wait, why would I want this? Doesn't Django have migrations built-in?
Isn't this the same thing?"

Yes, yes it does, and it mostly is. In fact, Django Evolution works
comfortably alongside Django's migrations, helping you get the best out of
both.

There are cases where you might want an alternative to migrations:

1. You're still stuck on Django 1.6 or earlier and need to make changes to
   your database.

   Django 1.6 is the last version without built-in support for migrations,
   and there are still codebases out there using it. Django Evolution can
   help keep upgrades manageable, and make it easier to transition all or
   part of your codebase to migrations when you finally upgrade.

2. You're distributing a self-installable web application, possibly used in
   large enterprises, where you have no control over when people are going to
   upgrade.

   Django's migrations assume some level of planning around when changes are
   made to the schema and when they're applied to a database. The more changes
   you make, and the more versions in-between what the user is running and
   what they upgrade to, the longer the upgrade time.

   If a customer is in control of when they upgrade, they might end up with
   *years* of migrations that need to be applied.

   Migrations apply one-by-one, possibly triggering the rebuild of a
   table many times during an upgrade. Django Evolution, on the other hand,
   can apply years worth of evolutions at once, optimized to perform as few
   table changes as possible. This can take days, hours or even *seconds* off
   the upgrade time.


.. _Django: https://www.djangoproject.com/


What versions of Django are supported?
--------------------------------------

Django Evolution 2.0 supports Django 1.6 through 3.1.

For older versions of Django, see Django Evolution 0.7.

There's built-in support for evolving SQLite, Postgres, MySQL, and MariaDB
databases.


I can't imagine anything better... How do I start?
--------------------------------------------------

We have a `bunch of documentation <https://django-evolution.readthedocs.org>`_
just for you!

There, you'll find out how to `install it`_, `configure it`_ for your project,
`generate evolutions`_, and `apply them`_.

Plus, answers_ to all^W some of your burning questions, like "how do these work
with migrations?" and "why is my syncdb/migrate command weird now?"

.. _Django: https://www.djangoproject.com/
.. _install it:
   https://django-evolution.readthedocs.io/en/latest/installation.html
.. _configure it:
   https://django-evolution.readthedocs.io/en/latest/installation.html
.. _generate evolutions:
   https://django-evolution.readthedocs.io/en/latest/writing-evolutions.html
.. _apply them:
   https://django-evolution.readthedocs.io/en/latest/commands/evolve.html
.. _answers:
   https://django-evolution.readthedocs.io/en/latest/faq.html


Who's using Django Evolution today?
-----------------------------------

There's dozens of us! Dozens!

At Beanbag_ we're using it in `Review Board`_, our open source code review
product, used by thousands of companies world-wide. So we know it works.
Review Board predated Django's migrations by a whole lot of years, and
continues to benefit from the optimized upgrade times of evolutions today.


.. _Beanbag: https://beanbaginc.com/
.. _Review Board: https://www.reviewboard.org/

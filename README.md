================
Django Evolution
================

An implementation of schema evolution for the Django web framework.

For details on how to use Django Evolution, read the tutorial/instructions
contained in docs/evolution.txt.

Most new Django projects may also want to take a look at South
(http://south.aeracode.org/), or the features built into Django 1.7.


When you run ./manage.py syncdb, Django will look for any new models that have
been defined, and add a database table to represent those new models. However,
if you make a change to an existing model, ./manage.py syncdb will not make any
changes to the database.

This is where Django Evolution fits in. Django Evolution is an extension to
Django that allows you to track changes in your models over time, and to update
the database to reflect those changes.

Django Evolution is a work in progress. The interface and usage of Django
Evolution is subject to change as we finess the details. If you'd like to help
out, check out the source and let us know what you think.

If you have any questions that aren't covered by the FAQ and/or documentation,
there is a mailing list where you may be able to get answers.


Using Django Evolution
----------------------

Django Evolution requires features that are only available in Django v1.4 or
higher.


Installation
------------

To install Django Evolution, simply run:

    $ easy_install -U django_evolution

You can also check out Django Evolution from the
[GitHub repository](https://github.com/beanbaginc/django-evolution).


Using Django Evolution in your project
--------------------------------------

1. Add `django_evolution` to the `INSTALLED_APPS` for your project
2. Run `./manage.py syncdb`
3. Make modifications to the model files in your project
4. Run `./manage.py evolve --hint --execute`

For a detailed description of the capabilities of Django Evolution,
please read the [FAQ][faq], and/or the [documentation][docs]

[faq]: https://github.com/beanbaginc/django-evolution/blob/master/docs/faq.txt
[docs]: https://github.com/beanbaginc/django-evolution/blob/master/docs/evolution.txt

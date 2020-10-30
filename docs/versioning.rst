.. _version-policy:

Project Versioning Policy
=========================

Beginning with 2.0, Django Evolution uses semantic versioning, in
``major.minor.micro`` form.

We will bump ``major`` any time there is a backwards-incompatible change to:

* Evolution definition format
* Compatibility with older versions of Django, Python, or databases
* The ``evolve`` management command's arguments or behavior
* :ref:`Public Python API <public-python-api>`

We will bump ``minor`` any time there's a new feature.

We will bump ``micro`` any time there's just bug or packaging fixes.

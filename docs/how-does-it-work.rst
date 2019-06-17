=================
How Does It Work?
=================

Django Evolution tracks all the apps in your Django project, recording
information on the structure of models, their fields, indexes, and so on.

When you make any change to a model that would need to be reflected in
the database, Django Evolution will tell you that you'll need an evolution
file to apply those changes, and will suggest one for you.

Evolution files describe one or more changes made to models in an app. They
can:

* Add fields
* Change the attributes on fields
* Rename fields
* Delete fields
* Change the indexes or constraints on a model
* Rename models
* Delete models
* Rename apps
* Delete apps
* Transition an app to Django's migrations
* Run arbitrary SQL

Django Evolution looks at the last-recorded state of your apps, the current
state, and the evolution files. If those evolution files are enough to update
the database to the current state, then Django Evolution will process them,
turning them into an optimized list of SQL statements, and apply them to the
database.

This can be done for the entire database as a whole, or for specific apps in
the database.

Since some apps (particularly Django's own apps) make use of migrations (on
Django 1.7 and higher), Django Evolution will also handle applying those
migrations. It will do this in cooperation with the evolution files that it
also needs to apply. However, it's worth pointing out that migrations are
never optimized the way evolutions are (this is currently a limitation in
Django).

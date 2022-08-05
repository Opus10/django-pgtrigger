.. _multi_db:

Multiple Database Support
=========================
``django-pgtrigger`` installs model triggers based on the
``db_for_write`` return value in database routers for multi-database
setups.
See `the Django docs <https://docs.djangoproject.com/en/3.1/topics/db/multi-db/#db_for_write>`__
for more information on ``db_for_write``.

If your Django application uses sharding or a database setup that involves
multiple write databases for a single model, triggers may not be installed properly.
If this is your case, please open an issue on
the project and explain your database setup.

.. note::

  All management commands and core functions take an optional ``database``
  argument to only run over a single database. Otherwise all commands run
  over all databases.

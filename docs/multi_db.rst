Multiple Database Support
=========================
``django-pgtrigger`` installs model triggers based on the
``db_for_write`` return value in the database routers for multi-database
setups.
See `these docs <https://docs.djangoproject.com/en/3.1/topics/db/multi-db/#db_for_write>`__
for more information on ``db_for_write``. By default, ``db_for_write``
returns the default database, meaning triggers are always installed on the
default database.

This behavior means that model triggers will only be installed on the write
database for configured models. All management commands and functions operate
in a similar fashion.

If your Django application uses sharding or a database setup that involves
multiple write databases for a single model, your application may experience
undesired trigger behavior. If this is your case, please open an issue on
the project. ``django-pgtrigger`` can be extended to install triggers
across all migrated databases, however, this feature was pushed back in
favor of it working with basic multi-database setups.

``django-pgtrigger`` installs triggers after migrations unless
the ``PGTRIGGER_INSTALL_ON_MIGRATE`` setting is ``False``. Similar to
Django's ``migrate`` command, only the default database has triggers installed
unless the ``migrate`` command is supplied with a ``--database`` argument.

If database routers change their respective write configurations,
``django-pgtrigger`` will uninstall any orphaned triggers and reinstall
them on the new table on the next installation of triggers.

.. note::

  All management commands and core functions take an optional ``database``
  argument to only run over a single database. Otherwise all commands run
  over all databases.

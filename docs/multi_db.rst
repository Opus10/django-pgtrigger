.. _multi_db:

Multiple Databases and Schemas
==============================

Multiple Databases
------------------

Triggers are migrated for multiple database just like models. If you define a
custom router, triggers will be installed based on ``allow_migrate``.
See the `the Django docs on multiple databases <https://docs.djangoproject.com/en/4.1/topics/db/multi-db/>`__
for more info.

If you use installation commands (see :ref:`commands`), the behavior is
slightly different.  ``django-pgtrigger``
uses the database returned by the router's ``db_for_write`` method to determine
the installation database. This is legacy behavior that will be updated in
a later version to match Django's migration behavior.

.. tip::

  All management commands take repeatable ``--database`` (``-d``) arguments to
  target specific databases.

Multiple Schemas
----------------

There are two common ways of using Postgres schemas in Django, both of which
work with ``django-pgtrigger``:

1. Create a database in ``settings.DATABASE`` for each schema, configuring the
   ``search_path`` in the ``OPTIONS``.
2. Use an app like `django-tenants <https://github.com/django-tenants/django-tenants>`__
   to dynamically set the ``search_path`` for a single database.

 When using the first approach, use the multi-database support detailed in
 the previous section. For the second approach, ``django-pgtrigger``
 comes with the ability to dynamically set the ``search_path``:

1. Pass ``--schema`` (``-s``) arguments for management
   commands. For example, this sets ``search_path`` to ``myschema,public``
   and shows trigger installation status relative to those schemas::

    python manage.py pgtrigger ls -s my_schema -s public

2. Programmatically set the search path with `pgtrigger.schema`.
   For example, this sets the ``search_path`` to ``myschema,public``::

    with pgtrigger.schema("myschema", "public"):
        # seach_path is set. Any more nested invocations of
        # pgtrigger.schema will append to the path

.. note::

  If you find yourself wrapping the ``django-pgtrigger`` API with `pgtrigger.schema`,
  open an issue and let us know about your use case. We may consider making it a
  first-class citizen in the API if it's common.
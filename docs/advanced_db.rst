.. _advanced_db:

Advanced Database Setups
========================

Here we cover details about more advanced database setups that
might impact how you use triggers.

Multiple Databases
------------------

Triggers are migrated for multiple database just like models. If you define a
custom router, triggers will be installed based on ``allow_migrate``.
See the `the Django docs on multiple databases <https://docs.djangoproject.com/en/4.1/topics/db/multi-db/>`__
for more info.

.. warning::

   If you migrate triggers and afterwards change the behavior of the router's
   ``allow_migrate``, you risk having orphaned triggers installed on tables.

The management commands and core installation functions work the same way,
targetting an individual database like Django's ``migrate`` command.
Each command can be supplied with a ``-d`` or ``--database`` option.

For example, ``python manage.py pgtrigger install --database other`` will
install all of the triggers on the ``other`` database.

If ``allow_migrate`` ignores a particular model for a database, the
installation status will show as ``UNALLOWED`` when using
``python manage.py pgtrigger ls``.

.. note::

   If you've configured ``settings.INSTALL_ON_MIGRATE``, triggers will
   be installed for the same database as the ``migrate`` command.

Dynamic runtime functions `pgtrigger.ignore`, `pgtrigger.schema`, and
`pgtrigger.constraints` operate on all postgres databases at once
unless the ``databases`` argument is provided.


Schemas
-------

There are two common ways of using Postgres schemas in Django, both of which
work with ``django-pgtrigger``:

1. Create a database in ``settings.DATABASES`` for each schema, configuring the
   ``search_path`` in the ``OPTIONS``.
2. Use an app like `django-tenants <https://github.com/django-tenants/django-tenants>`__
   to dynamically set the ``search_path`` for a single database.

When using the first approach, use the multi-database support detailed in
the previous section. For the second approach, ``django-pgtrigger``
comes with the following functionality to dynamically set the ``search_path``:

1. Pass ``--schema`` (``-s``) arguments for management
   commands. For example, this sets ``search_path`` to ``myschema,public``
   and shows trigger installation status relative to those schemas::

    python manage.py pgtrigger ls -s my_schema -s public

2. Programmatically set the search path with `pgtrigger.schema`.
   For example, this sets the ``search_path`` to ``myschema,public``::

    with pgtrigger.schema("myschema", "public"):
        # seach_path is set to "myschema,public". Any nested invocations of
        # pgtrigger.schema will append to the path if not currently
        # present

.. note::

  If you find yourself wrapping the ``django-pgtrigger`` API with `pgtrigger.schema`,
  open an issue and let us know about your use case. We may consider making it a
  first-class citizen in the API if it's common.

The final thing to keep in mind with multi-schema support is that `pgtrigger.ignore`
uses a special Postgres function for ignoring triggers that's installed under
the public schema. The function is always referenced with a fully-qualified name.

If you don't use the public schema, configure the schema with
``settings.PGTRIGGER_SCHEMA``. Setting this to ``None`` uses a relative path when
installing and calling the function.

Partitions
----------

``django-pgtrigger`` supports tables that use `Postgres table partitioning <https://www.postgresql.org/docs/current/ddl-partitioning.html>`__ with no additional configuration.

.. note::
   Row-level triggers are only available for partitioned tables in Postgres 13 and above.
   Triggers cannot be installed or uninstalled on a per-partition basis. Installing a trigger on a partitioned
   table installs it for all partitions.
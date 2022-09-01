.. _commands:

Commands
========

``django-pgtrigger`` comes with the ``python manage.py pgtrigger`` command,
which has several subcommands that are described below.

ls
--

List all triggers managed by ``django-pgtrigger``.

**Options**

[uris ...]
    Trigger URIs to list.

-d, --database  List triggers on this database.
-s, --schema  Use this schema as the search path. Can be provided multiple times.

**Ouput**

The following installation status markers are displayed:

- ``INSTALLED``: The trigger is installed and up to date
- ``OUTDATED``: The trigger is installed, but it has not been migrated
  to the current version.
- ``UNINSTALLED``: The trigger is not installed.
- ``PRUNE``: A trigger is no longer in the codebase and still installed.
- ``UNALLOWED``: Trigger installation is not allowed for this database.
  Only applicable in a multi-database environment.

Note that every installed trigger, including ones that will be pruned,
will show whether they are enabled or disabled. Disabled triggers are
installed but do not run.

install
-------

Install triggers. If no arguments are
provided, all triggers are installed and orphaned triggers are pruned.

**Options**

[uris ...]
    Trigger URIs to install.

-d, --database  Install triggers on this database.
-s, --schema  Use this schema as the search path. Can be provided multiple times.

uninstall
---------

Uninstall triggers. If no arguments are
provided, all triggers are uninstalled and orphaned triggers will be pruned.

.. danger::

    Running ``uninstall`` will globally uninstall triggers.
    If you need to temporarily ignore a trigger, see the :ref:`ignoring_triggers` section.

**Options**

[uris ...]
    Trigger URIs to uninstall.

-d, --database  Uninstall triggers on this database.
-s, --schema  Use this schema as the search path. Can be provided multiple times.

enable
------

Enable triggers.

**Options**

[uris ...]
    Trigger URIs to enable.

-d, --database  Enable triggers on this database.
-s, --schema  Use this schema as the search path. Can be provided multiple times.


disable
-------

Disable triggers.

.. danger::

    Running ``disable`` will globally disable the execution of triggers.
    If you need to temporarily ignore a trigger, see the :ref:`ignoring_triggers` section.

**Options**

[uris ...]
    Trigger URIs to enable.

-d, --database  Disable triggers on this database.
-s, --schema  Use this schema as the search path. Can be provided multiple times.

prune
-----

Uninstall any triggers managed by ``django-pgtrigger`` that are no longer in the codebase.

.. note::

  Pruning happens automatically when doing ``python manage.py pgtrigger install``
  or ``python manage.py pgtrigger uninstall``.

**Options**

-d, --database  Prune triggers on this database.
-s, --schema  Use this schema as the search path. Can be provided multiple times.

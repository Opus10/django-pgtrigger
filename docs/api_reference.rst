API Reference
=============

.. _commands:

Commands
~~~~~~~~

``django-pgtrigger`` comes with the ``python manage.py pgtrigger`` command,
which has several subcommands that are described below.

ls
--

Use ``python manage.py pgtrigger ls`` to list all triggers
managed by ``django-pgtrigger``. The installation status and trigger URI
will be shown.

The following are valid installation status markers:

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

.. tip::

  You can provide trigger URIs as arguments to ``python manage.py pgtrigger ls``
  to only list specific triggers. The URI is the last column returned
  by ``python manage.py pgtrigger ls``.

install
-------

Use ``python manage.py pgtrigger install`` to install triggers. If no arguments are
provided, all triggers are installed and any orphaned ones will be pruned.

You can provide trigger URIs as arguments to install specific triggers
or filter triggers on a database with the ``--database`` argument.

uninstall
---------

Uninstall has the same behavior as ``python manage.py pgtrigger install`` except triggers
will be uninstalled.

.. danger::

    Running ``uninstall`` will globally uninstall triggers.
    If you need to temporarily ignore a trigger, see the :ref:`ignoring_triggers` section.

enable
------

``python manage.py pgtrigger enable`` enables triggers. Similar to other commands,
one can provide trigger URIs or the database.

disable
-------

Disable has the same behavior as ``python manage.py pgtrigger enable`` except triggers
will be disabled.

.. danger::

    Running ``disable`` will globally disable the execution of triggers.
    If you need to temporarily ignore a trigger, see the :ref:`ignoring_triggers` section.

prune
-----

``python manage.py pgtrigger prune`` will uninstall any triggers managed
by ``django-pgtrigger`` that are no longer in the codebase.

.. note::

  Pruning happens automatically when doing ``python manage.py pgtrigger install``
  or ``python manage.py pgtrigger uninstall``.


Python Package
~~~~~~~~~~~~~~

Below are the core classes and functions of the ``pgtrigger`` module.

Level clause
------------

.. autodata:: pgtrigger.Row

  For specifying row-level triggers (the default)

.. autodata:: pgtrigger.Statement

  For specifying statement-level triggers

When clause
-----------
.. autodata:: pgtrigger.After

  For specifying ``AFTER`` in the when clause of a trigger

.. autodata:: pgtrigger.Before

  For specifying ``BEFORE`` in the when clause of a trigger

.. autodata:: pgtrigger.InsteadOf

  For specifying ``INSTEAD OF`` in the when clause of a trigger

Operation clause
----------------
.. autodata:: pgtrigger.Truncate
  
  For specifying ``TRUNCATE`` as the trigger operation

.. autodata:: pgtrigger.Delete

  For specifying ``DELETE`` as the trigger operation

.. autodata:: pgtrigger.Insert

  For specifying ``INSERT`` as the trigger operation

.. autodata:: pgtrigger.Update

  For specifying ``UPDATE`` as the trigger operation

.. autoclass:: pgtrigger.UpdateOf

Referencing clause
------------------

.. autoclass:: pgtrigger.Referencing

Timing clause
-------------

.. autodata:: pgtrigger.Immediate
  
  For specifying ``IMMEDIATE`` as the default timing for deferrable triggers

.. autodata:: pgtrigger.Deferred

  For specifying ``DEFERRED`` as the default timing for deferrable triggers

Conditions
----------
.. autoclass:: pgtrigger.Condition
.. autoclass:: pgtrigger.Q
.. autoclass:: pgtrigger.F
.. autoclass:: pgtrigger.IsDistinctFrom
.. autoclass:: pgtrigger.IsNotDistinctFrom

Triggers
--------
.. autoclass:: pgtrigger.Trigger
.. autoclass:: pgtrigger.Protect
.. autoclass:: pgtrigger.SoftDelete
.. autoclass:: pgtrigger.FSM
.. autoclass:: pgtrigger.UpdateSearchVector

Runtime execution
-----------------
.. autofunction:: pgtrigger.constraints
.. autofunction:: pgtrigger.ignore
.. autofunction:: pgtrigger.schema

Registry
--------
.. autofunction:: pgtrigger.register
.. autofunction:: pgtrigger.registered

Installation
------------
.. autofunction:: pgtrigger.install
.. autofunction:: pgtrigger.uninstall
.. autofunction:: pgtrigger.enable
.. autofunction:: pgtrigger.disable
.. autofunction:: pgtrigger.prunable
.. autofunction:: pgtrigger.prune

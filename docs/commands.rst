.. _commands:

Commands
========

``django-pgtrigger`` comes with the ``manage.py pgtrigger`` command. It
can be called with the following subcommands.

ls
--

Use ``manage.py pgtrigger ls`` to list all triggers that are actively
managed by ``django-pgtrigger``. The trigger URI, database, installation status,
and whether the trigger is enabled or disabled will be shown.

The following are valid installation status markers:

- ``INSTALLED``: The trigger is installed and up to date
- ``OUTDATED``: The trigger is installed, but it is outdated. New changes
  need to be applied with ``manage.py pgtrigger install``.
- ``UNINSTALLED``: The trigger is not active and is not yet installed.
- ``PRUNE``: A trigger that was formerly installed by ``django-pgtrigger``
  is no longer in the codebase and needs to be pruned. Pruning can be done
  with ``manage.py pgtrigger prune`` or by doing a full
  ``manage.py pgtrigger install`` or ``manage.py pgtrigger uninstall``.
  Note that these triggers are still active and running and are no different
  than installed triggers.

Note that every installed trigger, including ones that will be pruned,
will show whether they are enabled or disabled. Disabled triggers are
installed but do not run, and they have to be manually re-enabled.
Enabling and disabling of triggers can be performed with
``manage.py pgtrigger enable`` and ``manage.py pgtrigger disable``.

.. note::

  You can provide trigger URIs as arguments to ``manage.py pgtrigger ls``
  to only list specific triggers. The URI is the first column returned
  by ``manage.py pgtrigger ls``. You can also only list triggers on
  a single database with the ``--database`` option.

install
-------

Use ``python manage.py install`` to install triggers. If no arguments are
provided, it will try to install all triggers that are not currently installed.
Messages will be printed for every installed trigger. When executed with
no arguments, any triggers that were previously installed by ``django-pgtrigger``
but no longer in the codebase will be pruned.

You can provide trigger URIs as arguments to install specific triggers
or filter triggers on a database with the ``--database`` argument.
Trigger URIs can be found with the ``manage.py pgtrigger ls`` command.

uninstall
---------

Uninstall has the same behavior as ``manage.py pgtrigger install`` except triggers
will be uninstalled.

enable
------

``manage.py pgtrigger enable`` will enable all triggers. All triggers
that were previously disabled will be printed when enabled. In contrast
to ``manage.py pgtrigger install``, no previously managed triggers will
be pruned.

Similar to other commands, one can provide trigger URIs as arguments or
the database.
Trigger URIs can be found with the ``manage.py pgtrigger ls`` command.

disable
-------

Disable has the same behavior as ``manage.py pgtrigger enable`` except triggers
will be disabled.

prune
-----

``manage.py pgtrigger prune`` will uninstall any triggers previously managed
by ``django-pgtrigger`` that are no longer in the codebase.

.. note::

  Pruning happens automatically when doing ``manage.py pgtrigger install``
  or ``manage.py pgtrigger uninstall`` with no additional arguments.

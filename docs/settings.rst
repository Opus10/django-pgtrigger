.. _settings:

Settings
========

Below are all settings for ``django-pgtrigger``.

PGTRIGGER_INSTALL_ON_MIGRATE
----------------------------

If ``True``, ``python manage.py pgtrigger install`` will run
automatically after ``python manage.py migrate``. The trigger install
command will use the same database as the migrate command.
This setting is unnecessary if ``PGTRIGGER_MIGRATIONS`` is ``True``.

**Default** ``False``

.. warning::

    There are known issues with this approach, such as having
    trigger installation issues when reversing migrations.
    This is a secondary way to install triggers if migrations or model meta
    options aren't desired.

PGTRIGGER_MIGRATIONS
--------------------

If ``False``, triggers will not be added to migrations
when running ``python manage.py makemigrations``.
Triggers will need to be installed manually or
with ``settings.PGTRIGGER_INSTALL_ON_MIGRATE``.

**Default** ``True``

PGTRIGGER_MODEL_META
--------------------

If ``False``, triggers cannot be specified
in the ``triggers`` attribute of model ``Meta`` options.
Migrations will also be disabled.
Triggers will need to be registered to
models with `pgtrigger.register` and installed manually or
with ``settings.PGTRIGGER_INSTALL_ON_MIGRATE``.

**Default** ``True``

.. warning::

    Turning this off will result in an error if a third-party
    application declares triggers in model ``Meta``.

PGTRIGGER_PRUNE_ON_INSTALL
--------------------------

If ``True``, running ``python manage.py install`` or ``python manage.py uninstall``
with no arguments will run ``python manage.py prune`` to prune orphaned triggers.

**Default** ``True``

PGTRIGGER_SCHEMA
----------------

The schema under which global database objects are stored, such as
the Postgres function used for ignoring triggers.

**Default** ``public``

PGTRIGGER_SCHEMA_EDITOR
-----------------------

If ``False``, the schema editor for migrations will not be patched.
Fields that are used in trigger conditions will result in migration
failures if their types are changed unless the triggers are
manually dropped ahead of time in the migration.

**Default** ``True``

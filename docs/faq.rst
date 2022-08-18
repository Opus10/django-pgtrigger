.. _faq:

Frequently Asked Questions
==========================

Triggers are scary, don't you think?
------------------------------------

If you have no problem with the database enforcing a uniqueness constraint, what's the problem with it enforcing other relevant problems? For example, a trigger can more reliably enforce state transitions of a column than application code.

The best way to get over fear of triggers is by writing basic test cases for them. You can also be sure they are installed by running ``python manage.py pgtrigger ls``.

How do I test triggers?
-----------------------

Manipulate your models in your test suite and verify the expected result happens. When a trigger fails, a ``django.db.utils.InternalError`` is raised.

If you've turned off migrations for your test suite, call `pgtrigger.install` after the database is set up or set ``settings.PGTRIGGER_INSTALL_ON_MIGRATE`` to ``True`` to ensure triggers are installed for your tests.

.. warning::

    Be sure the ``settings.PGTRIGGER_INSTALL_ON_MIGRATE`` setting is isolated to your test suite, otherwise it could
    cause unexpected problems in production when reversing migrations.

Why not just use Django signals?
--------------------------------

Django signals can easily be bypassed, and they don't fire in model operations like ``bulk_create``. If you are solving a database-level problem, such as protecting deletes, triggers are much more reliable.

My triggers are causing errors in migrations. What's going on?
--------------------------------------------------------------

If your triggers access mutliple tables across apps, you may encounter installation issues if you haven't declared those apps as ``dependencies`` in the migration file.

If you have ``settings.PGTRIGGER_INSTALL_ON_MIGRATE`` set to ``True``, this can also cause trigger installation issues when migrations are reversed. Your database tables should be fine, but triggers may be in an inconsistent state. You can use ``python manage.py pgtrigger ls`` to see the status of all triggers.

How do I disable triggers in my application?
--------------------------------------------

Use `pgtrigger.ignore` if you need to temporarily ignore triggers in your application (see :ref:`ignoring_triggers`). Only use the core installation commands if you want to disable or uninstall triggers globally (see the :ref:`commands` section).

Why are my triggers still outdated after being migrated?
--------------------------------------------------------

If ``python manage.py pgtrigger ls`` shows outdated triggers and ``makemigrations`` isn't showing changes, you are likely affected by a legacy issue that is a result of upgrading to version 3 or 4.

Although there are backwards compatibilities for outdated triggers that don't create migrations, it's best to run ``python manage.py pgtrigger install`` to ensure triggers are up to date.

My trigger can't be serialized for migrations. What do I do?
------------------------------------------------------------

If a third-party app or custom trigger throws a ``ValueError`` that says it cannot be serialized, that means it isn't
compatible with Django's migration system. In order to fix this, override ``get_init_vals`` on the trigger class that
fails. Return the arguments originally passed to ``__init__`` as a tuple of ``(args, kwargs)``
where ``args`` is a list of positional arguments and ``kwargs`` is a dictionary of keyword arguments.

Patches are causing my application to fail. How can I disable them?
-------------------------------------------------------------------

``django-pgtrigger`` patches the minimum amount of Django functionality necessary to integrate with the migration system and install triggers. If this causes errors in your application, try turning off the relevant settings:

* Set ``settings.PGTRIGGER_SCHEMA_EDITOR`` to ``False`` to prevent it from overriding the schema editor. Turning this off
  is mostly harmless, but you will have errors installing triggers if column types of trigger conditions are altered.

* Set ``settings.PGTRIGGER_MIGRATIONS`` to ``False`` to completely turn off integration with the migration system. You will
  need to manually install triggers or set ``settings.PGTRIGGER_INSTALL_ON_MIGRATE`` to ``True`` to always install triggers
  after migrations. Note that this approach has limitations and bugs such as reversing migrations.

* Set ``settings.PGTRIGGER_MODEL_META`` to ``False`` to disable specifying triggers in model ``Meta``. You must explicitly
  register every trigger with `pgtrigger.register`, and triggers on third-party models may not be discovered. Integration 
  with the migration system will also be turned off as a result.

How do I migrate to version 3.0?
--------------------------------

Version 3 integrates with the migration system and also drops the need for configuring ``django-pgconnection`` for using `pgtrigger.ignore`. It also fully supports the ``Meta.triggers`` syntax for registering triggers.

The majority of users can simply run ``python manage.py makemigrations`` after upgrading if you have no triggers registered to third-party models or many-to-many default "through" models. Read below for more details on the upgrades, and follow the special instructions if any of the former cases apply to you.

Integration with Django migrations
**********************************

All triggers now appear in migrations when running ``python manage.py makemigrations``. Triggers from version 2 will appear as new ``AddTrigger`` operations. They will succeed when running ``migrate`` even if previously installed. Remember, however, that triggers will be deleted if the migrations are reversed.

Almost all users can simply run ``python manage.py makemigrations`` after upgrading. If, however, you have triggers on third-party models or many-to-many default "through" models, use these instructions to migrate them:

1. If you already ran ``python manage.py makemigrations``, delete any new migrations made for these third-party apps.
2. Declare proxy models for the third-party or many-to-many "through" models, register triggers in the ``Meta.triggers``, and call ``python manage.py makemigrations``. See code examples in the :ref:`advanced_installation` section.

If you'd like to keep the legacy installation behavior, set ``settings.PGTRIGGER_MIGRATIONS`` to ``False`` to turn off trigger migrations and set ``settings.PGTRIGGER_INSTALL_ON_MIGRATE`` to ``True`` so that triggers are always installed at the end of ``python manage.py migrate``.

Dropping of ``django-pgconnection`` dependency
**********************************************

`pgtrigger.ignore` previously required that ``django-pgconnection`` was used to configure the ``settings.DATABASES`` setting. ``django-pgconnection`` is no longer needed, and ``settings.DATABASES`` no longer needs to be wrapped in order
for `pgtrigger.ignore` to function properly.

New ``Meta.triggers`` syntax
****************************

Version 2.5 introduced the ability to register triggers on your model's ``Meta.triggers`` list. User can still use `pgtrigger.register` to register triggers programmatically, but it has been deprecated.

How do I migrate to version 4.0?
--------------------------------

Version 4 changes the behavior of multi-database and multi-schema usage. If you don't use multiple database and multiple
schemas, the only breaking API change that might affect you is ``pgtrigger.get`` being renamed to
`pgtrigger.registered`.

For multi-database setups, triggers are now installed on one database
at a time using the ``--database`` argument of management commands. Triggers are only ignored on a databases
based on the ``allow_migrate`` method of any installed routers. This mimics Django's behavior of installing tables.

If you use ``settings.PGTRIGGER_INSTALL_ON_MIGRATE``, triggers will only be installed for the database that was passed to
``python manage.py migrate``.

Version 4 adds support for multi-schema setups. See the :ref:`advanced_db` section for more information.

How can I contact the author?
-----------------------------

The primary author, Wes Kendall, loves to talk to users. Message him at `wesleykendall@protonmail.com <mailto:wesleykendall@protonmail.com>`__ for any feedback. He and other `Opus 10 engineers <https://opus10.dev>`__ do contracting work, so keep them in mind for your next Django project.

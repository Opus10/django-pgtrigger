.. _upgrading:

Upgrading
=========

Version 3
---------

Version 3 integrates with the migration system and also drops the need for configuring ``django-pgconnection`` for using `pgtrigger.ignore`. It also fully supports the ``Meta.triggers`` syntax for registering triggers.

The majority of users can simply run ``python manage.py makemigrations`` after upgrading if you have no triggers registered to third-party models or many-to-many default "through" models. Read below for more details on the upgrades, and follow the special instructions if any of the former cases apply to you.

Integration with Django migrations
**********************************

All triggers now appear in migrations when running ``python manage.py makemigrations``. Triggers from version 2 will appear as new ``AddTrigger`` operations. They will succeed when running ``migrate`` even if previously installed. Remember, however, that triggers will be deleted if the migrations are reversed.

Almost all users can simply run ``python manage.py makemigrations`` after upgrading. If, however, you have triggers on third-party models or many-to-many default "through" models, use these instructions to migrate them:

1. If you already ran ``python manage.py makemigrations``, delete any new migrations made for these third-party apps.
2. Declare proxy models for the third-party or many-to-many "through" models, register triggers in the ``Meta.triggers``, and call ``python manage.py makemigrations``. See code examples in the :ref:`advanced_installation` section.
3. Declaring proxy models will rename old triggers, leaving them in an orphaned state since they weren't previously managed by migrations. Ensure these old triggers are removed by doing any of the following:
    a. Make a ``migrations.RunPython`` operation at the end of your migration or in a new data migration that does ``call_command("pgtrigger", "prune")``. Note that ``call_command`` is imported from ``django.core.management``.
    b. OR run ``python manage.py pgtrigger prune`` after your deployment is complete
    c. OR set ``settings.PGTRIGGER_INSTALL_ON_MIGRATE`` to ``True`` for a short period of time in your settings. This will automatically prune those old triggers after deployment, and you can turn this setting back to ``False`` later.

If you'd like to keep the legacy installation behavior and turn off migrations entirely, set ``settings.PGTRIGGER_MIGRATIONS`` to ``False`` to turn off trigger migrations and set ``settings.PGTRIGGER_INSTALL_ON_MIGRATE`` to ``True`` so that triggers are always installed at the end of ``python manage.py migrate``.

Dropping of ``django-pgconnection`` dependency
**********************************************

`pgtrigger.ignore` previously required that ``django-pgconnection`` was used to configure the ``settings.DATABASES`` setting. ``django-pgconnection`` is no longer needed, and ``settings.DATABASES`` no longer needs to be wrapped in order
for `pgtrigger.ignore` to function properly.

New ``Meta.triggers`` syntax
****************************

Version 2.5 introduced the ability to register triggers on your model's ``Meta.triggers`` list. User can still use `pgtrigger.register` to register triggers programmatically, but it has been deprecated.

Version 4
---------

Version 4 changes the behavior of multi-database and multi-schema usage. If you don't use multiple database and multiple
schemas, the only breaking API change that might affect you is ``pgtrigger.get`` being renamed to
`pgtrigger.registered`.

For multi-database setups, triggers are now installed on one database
at a time using the ``--database`` argument of management commands. Triggers are only ignored on a databases
based on the ``allow_migrate`` method of any installed routers. This mimics Django's behavior of installing tables.

If you use ``settings.PGTRIGGER_INSTALL_ON_MIGRATE``, triggers will only be installed for the database that was passed to
``python manage.py migrate``.

Version 4 adds support for multi-schema setups. See the :ref:`advanced_db` section for more information.

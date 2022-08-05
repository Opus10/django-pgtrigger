.. _faq:

Frequently Asked Questions
==========================

How can I be sure triggers are working?
---------------------------------------

Triggers are not much different than constraints. Triggers are installed against your model tables, and they raise internal database exceptions in your Django app when errors happen. You can be sure they are working by writing tests.

How do I test triggers?
-----------------------

Manipulate your models in your test suite and verify the expected result happens. Similar to constraints, there is nothing magical about testing triggers. Keep in mind that when a trigger fails, a ``django.db.utils.InternalError`` is raised.

Why not just use Django signals?
--------------------------------

Django signals can easily be bypassed, and they don't fire in model operations like ``bulk_create``. If you are solving a database-level problem, such as protecting deletes, triggers are much more reliable.

Why does ``AddConstraint`` appear in migrations?
------------------------------------------------

``django-pgtrigger`` piggybacks off of Django model constraints to integrate with Django's migration system. When a trigger is added or removed, you will see ``AddConstraint`` or ``RemoveConstraint`` operations appear in migrations.

My triggers are causing errors in migrations. What's going on?
--------------------------------------------------------------

If your triggers access mutliple tables, keep in mind that you might need set these tables as dependencies for your migration.

How do I disable triggers in my application?
--------------------------------------------

Use `pgtrigger.ignore` if you need to temporarily ignore triggers in your application (see :ref:`ignoring_triggers`). Only use the core installation commands if you want to disable or uninstall triggers globally (see the :ref:`commands` section).

My trigger can't be serialized for migrations. What do I do?
------------------------------------------------------------

If a third-party app or custom trigger throws a ``ValueError`` that says it cannot be serialized, that means it isn't
compatible with Django's migration system. In order to fix this, override ``get_init_vals`` on the trigger class that
fails. Return the arguments originally passed to ``__init__`` as a tuple of ``(args, kwargs)``
where ``args`` is a list of positional arguments and ``kwargs`` is a dictionary of keyword arguments.

Patches are causing my application to fail. How can I disable them?
-------------------------------------------------------------------

``django-pgtrigger`` patches the minimum amount of Django functionality necessary to integrate with the migration system. If this causes errors in your application, the following settings can be disabled:

- ``PGTRIGGER_MODEL_META``: Setting this to ``False`` will disable the ability to specify triggers in model ``Meta``. You must explicitly register every trigger with `pgtrigger.register`.
- ``PGTRIGGER_MIGRATIONS``: Setting this to ``False`` will turn off integration with the migration system. You will need to manually install triggers or set ``PGTRIGGER_INSTALL_ON_MIGRATE`` to ``True`` to always install triggers after migrations.
- ``PGTRIGGER_PATCH_CHECKS``: Setting this to ``False`` will avoid patching Django's check framework. If, however, any of your trigger names aren't globally unique, you'll need to change them or silence the check another way.

How do I migrate to version 3.0?
--------------------------------

Version 3 integrates with the migration system and also drops the need for configuring ``django-pgconnection`` for using `pgtrigger.ignore`. It also fully supports the ``Meta.triggers`` syntax for registering triggers.

The majority of users can simply run ``python manage.py makemigrations`` after upgrading, but read below if you've configured triggers for third-party models or want to use new syntax for registering triggers.

Integration with Django migrations
**********************************

All triggers now appear in migrations when running ``python manage.py makemigrations``. Triggers from version 2 will appear as new ``AddConstraint`` operations and succeed when running ``migrate`` even if previously installed. Remember, however, that triggers will be deleted if the migrations are reversed.

Almost all users can simply run ``python manage.py makemigrations`` after upgrading. If, however, you have registered third-party models that have triggers, use these instructions to migrate them:

1. If you already ran ``python manage.py makemigrations``, delete any new migrations made in these third-party apps.
2. Running ``python manage.py pgtrigger makemigrations <third_party_app> <internal_app>``, where ``third_party_app`` is the app label of the third party app and ``internal_app`` is the app label where the migration file will be created. This ensures that the migrations remain in your project.

If you'd like to keep the legacy installation behavior, set ``PGTRIGGER_INSTALL_ON_MIGRATE`` to ``True`` to install all triggers at the end of migrations, and set ``PGTRIGGER_MIGRATIONS`` to ``False`` to turn off integration with the migration system.

Dropping of ``django-pgconnection`` dependency
**********************************************

`pgtrigger.ignore` previously required that ``django-pgconnection`` was used to configure the ``settings.DATABASES`` setting. ``django-pgconnection`` is no longer needed, and ``settings.DATABASES`` no longer needs to be wrapped in order
for `pgtrigger.ignore` to function properly.

New ``Meta.triggers`` syntax
****************************

Version 2.5 introduced the ability to register triggers on your model's ``Meta.triggers`` list. User can still use `pgtrigger.register` to register triggers programmatically.

How can I contact the author?
-----------------------------

The primary author, Wes Kendall, loves to talk to users. Message him at `wesleykendall@protonmail.com <mailto:wesleykendall@protonmail.com>`__ for any feedback. He and other `Opus 10 engineers <https://opus10.dev>`__ do contracting work, so keep them in mind for your next Django project.

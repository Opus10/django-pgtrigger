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

My trigger can't be serialized for migrations. What do I do?
------------------------------------------------------------

If a third-party app or custom trigger throws a ``ValueError`` that says it cannot be serialized, that means it isn't
compatible with Django's migration system. In order to fix this, override ``get_init_vals`` on the trigger class that
fails. Return the arguments originally passed to ``__init__`` as a tuple of ``(args, kwargs)``
where ``args`` is a list of positional arguments and ``kwargs`` is a dictionary of keyword arguments.

Patches are causing my application to fail. How can I disable them?
-------------------------------------------------------------------

``django-pgtrigger`` patches the minimum amount of Django functionality necessary to integrate with the migration system. If this causes errors in your application, set ``settings.PGTRIGGER_MIGRATIONS`` to ``False`` to turn off integration with the migration system. You will need to manually install triggers or set ``settings.PGTRIGGER_INSTALL_ON_MIGRATE`` to ``True`` to always install triggers after migrations.

If patching-related errors still happen, set ``settings.PGTRIGGER_MODEL_META`` to ``False`` to disable specifying triggers in model ``Meta``. You must explicitly register every trigger with `pgtrigger.register`, and triggers on third-party models may not be discovered.

How do I migrate to version 3.0?
--------------------------------

Version 3 integrates with the migration system and also drops the need for configuring ``django-pgconnection`` for using `pgtrigger.ignore`. It also fully supports the ``Meta.triggers`` syntax for registering triggers.

The majority of users can simply run ``python manage.py makemigrations`` after upgrading if you have no triggers registered to third-party models or many-to-many default "through" models. Read below for more details on the upgrades, and follow the special instructions if any of the former cases apply to you.

Integration with Django migrations
**********************************

All triggers now appear in migrations when running ``python manage.py makemigrations``. Triggers from version 2 will appear as new ``AddTrigger`` operations. They will succeed when running ``migrate`` even if previously installed. Remember, however, that triggers will be deleted if the migrations are reversed.

Almost all users can simply run ``python manage.py makemigrations`` after upgrading. If, however, you have triggers on third-party models or many-to-many default "through" models, use these instructions to migrate them:

1. If you already ran ``python manage.py makemigrations``, delete any new migrations made for these third-party apps.
2. Declare proxy models for the third-party models, register triggers in the ``Meta.triggers`` or those, and call ``python manage.py makemigrations``.
3. For triggers on a default many-to-many "through" models, create an unmanaged model with the database table of the "through" models. Add triggers to ``Meta.triggers`` and run ``python manage.py makemigrations``.

For 2) and 3), see more examples in the :ref:`advanced_installation` section.

If you'd like to keep the legacy installation behavior, set ``PGTRIGGER_MIGRATIONS`` to ``False`` to turn off trigger migrations and set ``PGTRIGGER_INSTALL_ON_MIGRATE`` to ``True`` so that triggers are always installed at the end of ``python manage.py migrate``.

Dropping of ``django-pgconnection`` dependency
**********************************************

`pgtrigger.ignore` previously required that ``django-pgconnection`` was used to configure the ``settings.DATABASES`` setting. ``django-pgconnection`` is no longer needed, and ``settings.DATABASES`` no longer needs to be wrapped in order
for `pgtrigger.ignore` to function properly.

New ``Meta.triggers`` syntax
****************************

Version 2.5 introduced the ability to register triggers on your model's ``Meta.triggers`` list. User can still use `pgtrigger.register` to register triggers programmatically, but it has been deprecated.

How can I contact the author?
-----------------------------

The primary author, Wes Kendall, loves to talk to users. Message him at `wesleykendall@protonmail.com <mailto:wesleykendall@protonmail.com>`__ for any feedback. He and other `Opus 10 engineers <https://opus10.dev>`__ do contracting work, so keep them in mind for your next Django project.

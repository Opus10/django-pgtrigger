.. _troubleshooting:

Troubleshooting
===============

Disabling migration integration
-------------------------------

See :ref:`turning_off_migrations` for how to disable the integration with
the migration system.

Trigger installation fails when migrating
-----------------------------------------

If your triggers access mutliple tables across apps, you may encounter installation issues if you haven't declared those apps as ``dependencies`` in the migration file. `See the Django docs <https://docs.djangoproject.com/en/4.1/topics/migrations/#dependencies>`__ for
more information.

If you have ``settings.PGTRIGGER_INSTALL_ON_MIGRATE`` set to ``True``, this can also cause trigger installation issues when migrations are reversed. Although database tables are properly reversed, triggers may be in an inconsistent state. You can use ``python manage.py pgtrigger ls`` to see the status of all triggers.

Triggers are still outdated after migrating
-------------------------------------------

If ``python manage.py pgtrigger ls`` shows outdated triggers and ``makemigrations`` isn't showing changes, you are likely affected by a legacy issue that has been addressed as of version 4.5. The issue is normally harmless and can be corrected by upgrading or
running ``python manage.py pgtrigger install`` to ensure triggers are up to date.

Patches are causing the application to fail
-------------------------------------------

``django-pgtrigger`` patches the minimum amount of Django functionality necessary to integrate with the migration system and install triggers. If this causes errors in your application, try turning off the relevant settings:

* Set ``settings.PGTRIGGER_SCHEMA_EDITOR`` to ``False`` to prevent it from overriding the schema editor. Turning this off
  is mostly harmless, but you will have errors installing triggers if column types of trigger conditions are altered.

* Set ``settings.PGTRIGGER_MIGRATIONS`` to ``False`` to completely turn off integration with the migration system. You will
  need to manually install triggers or set ``settings.PGTRIGGER_INSTALL_ON_MIGRATE`` to ``True`` to always install triggers
  after migrations. Note that this approach has limitations and bugs such as reversing migrations.

* Set ``settings.PGTRIGGER_MODEL_META`` to ``False`` to disable specifying triggers in model ``Meta``. You must explicitly
  register every trigger with `pgtrigger.register`, and triggers on third-party models may not be discovered. Integration 
  with the migration system will also be turned off as a result.

All triggers were updated at once
---------------------------------

A few updates, such as version 4.5, change the underlying SQL of triggers. This in turn causes all of the
triggers to be updated when running ``python manage.py makemigrations``.

Version 4.5 made significant changes to the migration system integration to avoid this needing to happen
in the future.

Trigger migrations stall
------------------------

When a trigger is dropped or created, it alters the table, thus taking out the most exclusive lock possible
and blocking reads the table.

Migrations run in a transaction by default, meaning locks will be held until the end of the entire migration.
If later operations in the migration block on acquiring locks, the previous locks will remain held until
the end. This can cause extended downtime for an application.

If your migration isn't doing any other table alterations such as adding columns, you can alleviate
lock contention as follows:

1. Remove any ``RemoveTrigger`` operations if the trigger is only being updated in the migration.
   The ``AddTrigger`` operations are idempotent, so dropping them before adding them is not necessary.
2. Once all of the ``RemoveTrigger`` operations are gone, you can set ``atomic = False`` on the migration
   (`see the Django docs <https://docs.djangoproject.com/en/4.1/topics/migrations/#transactions>`__) to
   avoid unnecessary lock consumption.

.. danger::

    Be sure you understand exactly what is happening when adding ``atomic=False`` to a migration.
    If there are other migration operations in the file, such as adding fields, it could create errors
    that are difficult to fix if the migration fails midway. If you don't remove the ``RemoveTrigger``
    operations, you also might create a scenario where your triggers aren't installed for a period
    of time.
.. _advanced_installation:

Advanced Installation
=====================

Third-party models
------------------

Install triggers on third-party models by declaring them on a proxy model.
For example, here we protect Django's ``User`` models from being deleted:

.. code-block:: python

    class UserProxy(User):
        class Meta:
            proxy = True
            triggers = [
                pgtrigger.Protect(name='protect_deletes', operation=pgtrigger.Delete)
            ]

Note that this syntax does not work for default many-to-many "through" models.
See the next section for details.

Default many-to-many "through" models
-------------------------------------

When defining a many-to-many relationship, Django uses a separate relationship model,
called the "through" model. If you want to install triggers for the default
through model, you will need to define them on an unmanaged model that uses the
database table of the through model.

Here we protect Django ``User`` group relationships from being deleted:


.. code-block:: python

    class UserGroupTriggers(models.Model):
        class Meta:
            managed = False
            db_table = User.groups.through._meta.db_table
            triggers = [
                pgtrigger.Protect(name='protect_deletes', operation=pgtrigger.Delete)
            ]

Although ``django-pgtrigger`` allows installing triggers against unmanaged models,
we recommend only using this feature for this specific use case.

.. note::

    If a third-party through model is used, be sure to set the ``dependencies``
    of the migration to depend on the third-party app's last migration.

Programmatically registering triggers
-------------------------------------

Triggers can be registered programmatically with `pgtrigger.register`.
It can be used as a decorator on a model or called like so:

.. code-block:: python

    # Register a protection trigger for a model
    pgtrigger.register(pgtrigger.Protect(...))(MyModel)

.. warning::

    Although triggers can be registered programmatically, we don't recommend doing
    this except for advanced use cases. Registering a trigger
    to a model of a third-party app will create migrations in that app. This could
    result in migrations not being added to your codebase, which can result in triggers
    not being installed.

Turning off migration integration
---------------------------------

``django-pgtrigger`` patches Django's migration system so that triggers are installed
and updated in migrations. If this is undesirable, you can
disable the migration integration by setting ``settings.PGTRIGGER_MIGRATIONS`` to
``False``. After this, you are left with two options:

1. Manually install triggers with the commands detailed in the next section.
2. Run trigger installation after every ``python manage.py migrate`` by setting
   ``settings.PGTRIGGER_INSTALL_ON_MIGRATE`` to ``True``. Keep in mind that
   reversing migrations can cause issues when installing triggers this way.

Manual installation, enabling, and disabling
--------------------------------------------

.. warning::

    Installing, uninstalling, enabling, and disabling triggers are global operations
    that call ``ALTER`` on the table. These should never be called in application code,
    and they will also interfere with migrations. Only use them when absolutely necessary or
    when manually managing trigger installations outside of migrations.
    If you want to temporarily ignore a trigger in an application, see the
    :ref:`ignoring_triggers` section.

Sometimes one may need to manage installed triggers outside of the Django migration system
or turn off migrations by setting ``settings.PGTRIGGER_MIGRATIONS`` to ``False``.
The following functions manage trigger installation, and each one has an associated management
command in the :ref:`commands` section:

* `pgtrigger.install`: Install triggers
* `pgtrigger.uninstall`: Uninstall triggers
* `pgtrigger.enable`: Enable triggers
* `pgtrigger.disable`: Disable triggers
* `pgtrigger.prune`: Uninstall triggers created by ``django-pgtrigger``
  that are no longer in the codebase.

Showing installation status
---------------------------

Use ``python manage.py pgtrigger ls`` to see the installation status of individual triggers
or all triggers at once.

Triggers can be in one of three installation states: ``INSTALLED``, ``UNINSTALLED``, or ``PRUNED``.
When in a ``PRUNED`` state, the trigger is installed but no longer exists in the application.

Triggers are also either ``ENABLED`` or ``DISABLED``. Triggers are enabled by default unless a user
explicitly disables it after installation. Once disabled, triggers must be enabled
again to run.

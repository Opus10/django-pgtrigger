.. _advanced_installation:

Advanced Installation
=====================

Third-party models
------------------

Install triggers on third-party models by declaring them on a proxy model.
For example, here we protect Django's ``User`` model from being deleted:

.. code-block:: python

    class UserProxy(User):
        class Meta:
            proxy = True
            triggers = [
                pgtrigger.Protect(name='protect_deletes', operation=pgtrigger.Delete)
            ]

Default many-to-many "through" models
-------------------------------------

Similar to third-party models, we can also install triggers against default
many-to-many "through" models by using a proxy model. 
Here we protect Django ``User`` group relationships from being deleted:

.. code-block:: python

    class UserGroupTriggers(User.groups.through):
        class Meta:
            proxy = True
            triggers = [
                pgtrigger.Protect(name='protect_deletes', operation=pgtrigger.Delete)
            ]


.. warning::

    Django doesn't fully support making proxy models from default through relationships.
    Reversing migrations can sometimes throw ``InvalidBases`` errors.
    We recommend creating a custom through model when possible. See
    the `Django docs on making custom "through" models <https://docs.djangoproject.com/en/4.0/topics/db/models/#extra-fields-on-many-to-many-relationships>`__.

Declaring triggers in base models
---------------------------------

Triggers can be declared in an abstract model and inherited. Here is a base model for
soft-delete models:

.. code-block:: python

    class BaseSoftDelete(models.Model):
        is_active = models.BooleanField(default=True)

        class Meta:
            abstract = True
            triggers = [pgtrigger.SoftDelete(name="soft_delete", field="is_active")]

Keep in mind that ``Meta`` class inheritance follows standard Django convention. If
the child model defines a ``Meta`` class, you will need to inherit the parent's
``Meta`` class like so:

.. code-block:: python

    class ChildModel(BaseSoftDelete):
        class Meta(BaseSoftDelete.Meta):
            ordering = ["is_active"]

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

.. _turning_off_migrations:

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

.. warning::

    There are known issues with installing triggers after migrations that
    cannot be fixed. For example, reversing migrations can result in trigger
    installation errors, and race conditions can happen if triggers are
    installed after the underlying tables have been migrated.

Manual installation, enabling, and disabling
--------------------------------------------

The following commands allow one to manually manage trigger installation
and are detailed more in the :ref:`commands` section:

.. danger::

    The commands are are global operations. Use these commands with extreme caution, especially if
    the triggers are managed by migrations. If you need to temporarily ignore
    a trigger inside your application, see the
    :ref:`ignoring_triggers` section.


* ``python manage.py pgtrigger install``: Install triggers
* ``python manage.py pgtrigger uninstall``: Uninstall triggers
* ``python manage.py pgtrigger enable``: Enable triggers
* ``python manage.py pgtrigger disable``: Disable triggers
* ``python manage.py pgtrigger prune``: Uninstall triggers created by ``django-pgtrigger``
  that are no longer in the codebase.


Showing installation status
---------------------------

Use ``python manage.py pgtrigger ls`` to see the installation status of individual triggers
or all triggers at once. View the :ref:`commands` section for descriptions of the different
installation states.
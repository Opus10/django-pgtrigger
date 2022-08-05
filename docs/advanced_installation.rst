.. _advanced_installation:

Advanced Installation
=====================

Third-party models
------------------

Declare triggers on third-party models by making a
proxy model. Use the ``python manage.py pgtrigger makemigrations``
command to install them instead of the built-in ``python manage.py makemigrations``.

.. warning::

    If you have previously called ``python manage.py makemigrations`` with third-party triggers,
    a migration file will be stored in the third-party app instead of your project. You will need
    to delete this migration file for correct behavior.

Here we make a proxy model for Django's ``auth.User`` model and register
a protection trigger:

.. code-block:: python

    class UserProxy(User):
        class Meta:
            proxy = True
            triggers = [
                pgtrigger.Protect(name='protect_deletes', operation=pgtrigger.Delete)
            ]

After this, we call ``python manage.py pgtrigger makemigrations``, which takes the
third-party app label with triggers (in our case, ``auth``) and the internal app label where the migrations
are stored (in our case, ``internal``)::

    python manage.py pgtrigger makemigrations auth internal

After this, ``python manage.py migrate`` will install the trigger. Subsequent calls to
``python manage.py makemigrations`` will also avoid picking up the triggers from the third-party
app.

Programmatically registering triggers
-------------------------------------

Triggers can be registered programmatically with `pgtrigger.register`.
It can be used as a decorator on a model or called like so:

.. code-block:: python

    # Register a protection trigger for Django's User model
    pgtrigger.register(pgtrigger.Protect(...))(User)

.. note::

    Be sure that triggers are registered via an app config's
    ``ready()`` method so that the registration happens exactly once.
    `See the Django docs <https://docs.djangoproject.com/en/3.0/ref/applications/#django.apps.apps.ready>`__.


Manual installation, enabling, and disabling
--------------------------------------------

.. warning::

    Installing, uninstalling, enabling, and disabling triggers are global operations
    that call ``ALTER`` on the table. These should never be called in application code,
    and they interfere with migrations. Only use them when absolutely necessary or
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

If you simply want to see the status of all installed triggers,
run ``python manage.py pgtrigger ls``.

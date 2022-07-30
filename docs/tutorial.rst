.. _tutorial:

Tutorial
========

Overview
~~~~~~~~

Postgres triggers provide the ability to specify database actions
that should occur when operations happen in the database (INSERT, UPDATE,
DELETE, TRUNCATE) on certain conditions of the affected rows.

The `pgtrigger.Trigger` object is the base class for all triggers.
Attributes of this class mirror the syntax required for
`making a Postgres trigger <https://www.postgresql.org/docs/current/sql-createtrigger.html>`__.

The ``django-pgtrigger`` library is designed so that users only need to use
Python and Django idioms for registering common triggers on models.
More advanced users, however, can always
directly write the raw PL/pgSQL dialect used for Postgres triggers.

Here are all of basic attributes of triggers that you will use when
using just about any of the triggers in this library:

* **name**

    The identifying name of trigger. Is unique for every model and must
    be <= 47 characters. The trigger name is used for
    performing trigger management operations and must be provided.

* **when**

    When the trigger should happen. Can be one of
    `pgtrigger.Before` or `pgtrigger.After`
    to execute the trigger before or after an operation.
    One can use `pgtrigger.InsteadOf` for row-level operations of a
    view.

    .. note::

        `pgtrigger.Before` and `pgtrigger.After` can be used on SQL views
        as well as tables under some circumstances. See
        `the docs <https://www.postgresql.org/docs/12/sql-createtrigger.html>`__
        for a breakdown of when these constructs can be used for various types of
        operations.

* **operation**

    The operation which triggers execution of the trigger function.
    This can be one of `pgtrigger.Update`,
    `pgtrigger.Insert`, `pgtrigger.Delete`,
    `pgtrigger.Truncate`, or `pgtrigger.UpdateOf`.
    All of these can be ``OR`` ed
    together (e.g.  ``pgtrigger.Insert | pgtrigger.Update``)
    to configure triggering on a combination of operations.

    .. note::

        `pgtrigger.UpdateOf` is triggered when columns appear in an ``UPDATE``
        statement. It will not be triggered if other triggers edit columns.
        See the notes in the
        `Postgres docs <https://www.postgresql.org/docs/12/sql-createtrigger.html>`__
        for more information about this use case.

    .. note::

        Some conditions cannot be combined together for a valid trigger. For
        example, `pgtrigger.UpdateOf` cannot be combined with other
        operations.

* **condition** *(optional)*

    An optional condition on which the trigger is executed based on the ``OLD``
    and ``NEW`` row variables that are part of the trigger.

    One can use the `pgtrigger.Condition` class to write a free-form
    clause (e.g. ``OLD.value = "value"``). The `pgtrigger.Q`
    condition also mimics Django's ``Q`` object to specify a filter clause
    on the affected rows.
    For example, a condition of ``pgtrigger.Q(old__value='hello')``
    will only trigger when the old row's ``value`` field is ``hello``.

    .. note::

        Be sure to familiarize yourself with ``OLD`` and ``NEW`` when
        writing conditions by consulting the `Postgres docs <https://www.postgresql.org/docs/current/plpgsql-trigger.html>`__.
        For example,
        the ``OLD`` row in `pgtrigger.Insert` triggers is always ``NULL`` and the
        ``NEW`` row in `pgtrigger.Delete` triggers is always ``NULL``. ``OLD``
        and ``NEW`` is always ``NULL`` for `pgtrigger.Statement` triggers as well.
        One must keep these caveats in mind when constructing triggers
        to avoid unexpected behavior.


Here are the more advanced attributes of triggers that you will want to
know about when writing more complex triggers or writing your own
trigger functions.


* **func**

    The raw PL/pgSQL function that is executed.


    .. note::

        This is *not* the entire declared trigger function, but rather
        the snippet of PL/pgSQL that is nested in the
        ```DECLARE ... BEGIN ... END``` portion of the trigger.

* **declare** *(optional)*

    If the trigger requires additional variable declarations, they
    can be defined as a list of (variable_name, variable_type) tuples.
    For example ``declare=[('my_var_1', 'BOOLEAN'), ('my_var_2', 'JSONB')]``

* **level** *(optional, default=pgtrigger.Row)*

    Declares if the trigger fires for every row (`pgtrigger.Row`) or
    every statement (`pgtrigger.Statement`). Defaults to `pgtrigger.Row`.

* **referencing** *(optional)*

    When constructing a statement-level trigger, allows one to reference
    the ``OLD`` and ``NEW`` rows as transition tables using
    the `pgtrigger.Referencing` construct. For example,
    ``pgtrigger.Referencing(old='old_table_name', new='new_table_name')``
    will make an ``old_table_name`` and ``new_table_name`` table available
    as transition tables in the statement-level trigger. See
    `this <https://dba.stackexchange.com/a/177468>`__ for an additional
    explanation on the referencing construct and read the trigger cookbook
    later for an example.


    .. note::

        The ``REFERENCING`` construct for statement-level triggers is only available
        in Postgres10 and up.


Defining and installing triggers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Triggers are defined in the ``triggers`` attribute of the model ``Meta``
class.

For example, this trigger definition protects this model from being
deleted:

.. code-block:: python

    from django.db import models
    import pgtrigger


    class CannotDelete(models.Model):
        class Meta:
            triggers = [
                pgtrigger.Protect(name='protect_deletes', operation=pgtrigger.Delete)
            ]

Triggers are installed automatically when running
``manage.py migrate``. If a trigger definition is removed from the project,
the triggers will be removed in the database. If the trigger
changes, the new one will be created and the old one will be dropped
during migrations.

If you want to register triggers on external models, install them manually,
or disable them, see the :ref:`advanced_installation` section for more details. 

Trigger cookbook
~~~~~~~~~~~~~~~~

Here are examples using built-in trigger classes and raw SQL.

Validating field transitions
----------------------------

Similar to how one can configure a finite state machine on
a model field with `django-fsm <https://github.com/viewflow/django-fsm>`__,
the `pgtrigger.FSM` ensures that a field can only do configured
transitions on update.

For example, this trigger ensures that the ``status`` field of a model
can only transition from "unpublished" to "published" and from
"published" to "inactive". Any other updates on the ``status`` field
will result in an exception:

.. code-block:: python

    class MyModel(models.Model):
        """Enforce valid transitions of the 'status' field"""
        status = models.CharField(max_length=32, default='unpublished')

        class Meta:
            triggers = [
                pgtrigger.FSM(
                    name='status_fsm',
                    field='status',
                    transitions=[
                        ('unpublished', 'published'),
                        ('published', 'inactive'),
                    ]
                )
            ]

.. note::

    Similar to other triggers, `pgtrigger.FSM` can be supplied with
    a condition to only enforce the state transitions when a condition
    is met.

.. note::

    The `pgtrigger.FSM` trigger currently only works for non-null
    ``CharField`` fields.

Keeping a field in-sync with another
------------------------------------

Here we create a `pgtrigger.Trigger` that runs before an update
or insert to ensure that two fields remain in sync.

.. code-block:: python

    import pgtrigger

    class MyModel(models.Model):
        int_field = models.IntField()
        in_sync_int = models.IntField(help_text='Stays the same as "int_field"')

        class Meta:
            triggers = [
                pgtrigger.Trigger(
                    name='keep_in_sync',
                    operation=pgtrigger.Update | pgtrigger.Insert,
                    when=pgtrigger.Before,
                    func='NEW.in_sync_int = NEW.int_field; RETURN NEW;',
                )
            ]

.. note::

    When writing a `pgtrigger.Before` trigger, be sure to return the row over
    which the operation should be applied. Returning no row will prevent the
    operation from happening (which can be useful for certain behavior).
    See `the docs here <https://www.postgresql.org/docs/current/plpgsql-trigger.html>`__
    for more information about this behavior.

Soft-delete models
------------------

A soft-delete model is one that sets a field on the model to a value
upon deletion instead of deleting the model from the database. For example, it is
common is set an ``is_active`` field on a model to ``False`` to soft
delete it.

The `pgtrigger.SoftDelete` trigger takes the field as an argument and
a value to set on delete. The value defaults to ``False``. For example:

.. code-block:: python

    import pgtrigger


    class SoftDeleteModel(models.Model):
        # This field is set to false when the model is deleted
        is_active = models.BooleanField(default=True)

        class Meta:
            triggers = [
                pgtrigger.SoftDelete(name='soft_delete', field='is_active')
            ]


    m = SoftDeleteModel.objects.create()
    m.delete()

    # The model will still exist, but it is no longer active
    assert not SoftDeleteModel.objects.get().is_active


In the above example, the boolean field "is_active" is set to ``False``
upon deletion. `pgtrigger.SoftDelete` works with nullable
``CharField``, ``IntField``, and ``BooleanField`` fields.

The `pgtrigger.SoftDelete` trigger allows one to do soft deletes at the
database level with no instrumentation in code at the application level.
This reduces the possibility of application error.

.. note::

    When using `pgtrigger.SoftDelete`, keep in mind that Django will still
    perform cascading operations to models that reference the soft-delete
    model. For example, if one has a model that foreign keys to
    ``SoftDeleteModel`` in the example with ``on_delete=models.CASCADE``, that
    model *will* be deleted by Django when the parent model is soft deleted.
    One can use ``models.DO_NOTHING`` if they wish for Django to not delete
    references to soft-deleted models.

Append-only models
------------------

Here we create an append-only model using the `pgtrigger.Protect`
trigger for the ``UPDATE`` and ``DELETE`` operations:

.. code-block:: python

    import pgtrigger
    from django.db import models


    class AppendOnlyModel(models.Model):
        my_field = models.IntField()

        class Meta:
            triggers = [
                pgtrigger.Protect(
                    name='protect_updates_and_deletes',
                    operation=(pgtrigger.Update | pgtrigger.Delete)
                )
            ]

.. note::

    This table can still be truncated, although this is not an operation
    supported by Django. One can still protect against this by adding the
    `pgtrigger.Truncate` operation.

Official interfaces
-------------------

`pgtrigger.Protect` triggers can be combined with `pgtrigger.ignore` to create
"official" interfaces for doing database operations in your application.

.. note::

    Ignoring triggers requires additional conifguration. See the
    :ref:`ignoring_triggers` section to learn more.

For example, let's protect inserts on our custom
``User`` model and force all engineers to use one common interface to
create users:

.. code-block:: python

    from django.db import models


    @pgtrigger.ignore('my_app.User:protect_inserts')
    def create_user(**kwargs):
        """
        This is the "official" interface for creating users. Any code
        that tries to create users and does not go through this interface
        will fail
        """
        return User.objects.create(**kwargs)


    class User(models.Model):
        class Meta:
            triggers = [
                pgtrigger.Protect(name='protect_inserts', operation=pgtrigger.Insert)
            ]

Users of this application must call ``create_user`` to create users. Any
other code that creates users will fail.


Dynamic deletion protection
---------------------------

Here we only allow models with a ``deletable`` flag to be deleted:

.. code-block:: python

    import pgtrigger
    from django.db import models


    class DynamicDeletionModel(models.Model):
        is_deletable = models.BooleanField(default=False)

        class Meta:
            triggers = [
                pgtrigger.Protect(
                    name='protect_deletes',
                    operation=pgtrigger.Delete,
                    condition=pgtrigger.Q(old__is_deletable=False)
                )
            ]


Redundant update protection
---------------------------

Here we raise an error when someone makes a redundant update
to the database:

.. code-block:: python

    import pgtrigger
    from django.db import models


    class RedundantUpdateModel(models.Model):
        redundant_field1 = models.BooleanField(default=False)
        redundant_field2 = models.BooleanField(default=False)

        class Meta:
            triggers = [
                pgtrigger.Protect(
                    name='protect_redundant_updates',
                    operation=pgtrigger.Update,
                    condition=pgtrigger.Condition(
                        'OLD.* IS NOT DISTINCT FROM NEW.*'
                    )
                )
            ]


Freezing published models
-------------------------

Here we have a ``Post`` model with a ``status`` field. We only allow edits to this model
when it's not published.

.. code-block::

    import pgtrigger
    from django.db import models


    class Post(models.Model):
        status = models.CharField(default='unpublished')
        content = models.TextField()

        class Meta:
            triggers = [
                pgtrigger.Protect(
                    name='freeze_published_model',
                    operation=pgtrigger.Update,
                    condition=pgtrigger.Q(old__status='published')
                )
            ]


With the above, we've set a condition so that the ``Post`` model
can no longer be updated once the status field is "published".

We extend this example by allowing a published model to be able to
be edited, but only if that status is "inactive"

.. code-block::

    import pgtrigger
    from django.db import models


    class Post(models.Model):
        status = models.CharField(default='unpublished')
        content = models.TextField()

        class Meta:
            triggers = [
                pgtrigger.Protect(
                    name='freeze_published_model_allow_deactivation',
                    operation=pgtrigger.Update,
                    condition=(
                      pgtrigger.Q(old__status='published')
                      & ~pgtrigger.Q(new__status='inactive')
                )
            ]


In the above, we protect updates on any published posts unless
the update is transitioning the published post into an inactive state.


Versioned models
----------------

Here we write a `pgtrigger.Trigger`
that dynamically increments a model version before an update is
applied:

.. code-block:: python

    class Versioned(models.Model):
        """
        This model is versioned. The "version" field is incremented on every
        update, and users cannot directly update the "version" field.
        """
        version = models.IntegerField(default=0)
        char_field = models.CharField(max_length=32)

        class Meta:
            triggers = [
                # Protect anyone editing the version field directly
                pgtrigger.Protect(
                    name='protect_updates',
                    operation=pgtrigger.Update,
                    condition=pgtrigger.Q(old__version__df=pgtrigger.F('new__version'))
                ),
                # Increment the version field on changes
                pgtrigger.Trigger(
                    name='versioning',
                    when=pgtrigger.Before,
                    operation=pgtrigger.Update,
                    func='NEW.version = NEW.version + 1; RETURN NEW;',
                    # Don't increment version on redundant updates.
                    condition=pgtrigger.Condition('OLD.* IS DISTINCT FROM NEW.*')
                )
            ]

In the above, we've added two triggers:

1. One that protects updating the ``version`` field of the model. We don't
   want people tampering with this field.
2. A trigger that increments the ``version`` of the ``NEW`` row before
   an update is applied.

We return the ``NEW`` row in the second trigger definition. Postgres
uses this return value for the update operation. We've also ensured that
the versioning trigger only fires when anything in the row has changed.


.. note::

    The return value
    from `pgtrigger.Before` triggers is very important. If you return ``NULL``,
    it will tell Postgres to ignore the operation.


Statement-level triggers and transition tables
----------------------------------------------

Most of the terminology and examples around Postgres triggers have been
for "row-level" triggers, i.e. triggers that fire on events
for every row. However, row-level triggers can be expensive in some
circumstances if doing large bulk operations.

Statement-level triggers can be used to mitigate these scenarios. Triggers are executed
once per statement and can be configured with ``level=pgtrigger.Statement`` in
the trigger definition.

In statement level triggers, the ``OLD`` and ``NEW`` row variables are
always ``NULL``. We instead use "transition tables"
to access old and new rows.
One can use the `pgtrigger.Referencing` construct to write a statement-level trigger
that references the old and new rows. See `this example <https://dba.stackexchange.com/a/177468>`__
for more explanations about these constructs.

.. note::

    Transition tables are only available in Postgres 10 and up.

Here we have a history model that keeps track of changes to
a field for every update of the tracked table.
We create a statement-level trigger that logs the old and new
fields from a transition table to this persisted log model like so:

.. code-block:: python

    from django.db import models
    import pgtrigger


    class HistoryModel(models.Model):
        old_field = models.CharField(max_length=32)
        new_field = models.CharField(max_length=32)


    class TrackedModel(models.Model):
        field = models.CharField(max_length=32)

        class Meta:
            triggers = [
                pgtrigger.Trigger(
                    name='statement_level_log',
                    level=pgtrigger.Statement,
                    when=pgtrigger.After,
                    operation=pgtrigger.Update,
                    referencing=pgtrigger.Referencing(old='old_values', new='new_values'),
                    func=f'''
                        INSERT INTO {HistoryModel._meta.db_table}(old_field, new_field)
                        SELECT
                            old_values.field AS old_field,
                            new_values.field AS new_field
                        FROM old_values
                            JOIN new_values ON old_values.id = new_values.id;
                        RETURN NULL;
                    ''',
                )
            ]


With this trigger definition, we'll now have the following happen with only
one additional query in the trigger:

.. code-block:: python

    TrackedModel.objects.bulk_create([LoggedModel(field='old'), LoggedModel(field='old')])

    # Update all fields to "new"
    TrackedModel.objects.update(field='new')

    # The trigger should have tracked these updates
    print(HistoryModel.values('old_field', 'new_field'))

    >>> [{
      'old_field': 'old',
      'new_field': 'new'
    }, {
      'old_field': 'old',
      'new_field': 'new'
    }]

.. note::

    Check out `django-pghistory <https://django-pghistory.readthedocs.io>`__
    if you want automated history tracking built on top of
    ``django-pgtrigger``.


Tracking model history and changes
----------------------------------

``django-pgtrigger`` can be used to snapshot all model changes, snapshot
changes whenever a particular change happens, and even attach context from
your application (e.g. the authenticated user) to the triggered event.

Historical tracking and auditing is a problem that is going to be different
for every organization's needs. Because of the scope of this problem, we
have created a history tracking library called
`django-pghistory <https://django-pghistory.readthedocs.io>`__
that solves common needs for doing model change tracking. It is implemented
using ``django-pgtrigger``. Check out
the `docs here <https://django-pghistory.readthedocs.io>`__.


.. _ignoring_triggers:

Ignoring trigger execution dynamically
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use `pgtrigger.ignore` to dynamically ignore a trigger in a single thread of execution.
Below we ignore deletion protection:

.. code-block:: python

    from django.db import models
    import pgtrigger


    class CannotDelete(models.Model):
        class Meta:
            triggers = [
                pgtrigger.Protect(name='protect_deletes', operation=pgtrigger.Delete)
            ]


    # Bypass deletion protection
    with pgtrigger.ignore('my_app.CannotDelete:protect_deletes'):
        CannotDelete.objects.all().delete()

As shown above, `pgtrigger.ignore` takes a trigger URI that is formatted as
``{app_label}.{model_name}:{trigger_name}``. Multiple trigger URIs can
be given to `pgtrigger.ignore`, and `pgtrigger.ignore` can be nested.
If no triggers are provided, all triggers are ignored.

When used, `django-pgconnection <https://django-pgconnection.readthedocs.io>`__
dynamically sets a Postgres variable that the trigger understands. This allows us
to ignore a trigger's execution for a single thread rather than disabling it globally.

To use this feature, you will need to wrap ``settings.DATABASES``
with ``pgconnection.configure()`` in ``settings.py`` like so:

.. code-block:: python

    import pgconnection

    DATABASES = pgconnection.configure({
        'default': {
            # default database config..
        }
    })

.. _advanced_installation:

Advanced trigger installation guide
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Manual installation and disabling
---------------------------------

.. warning::

    Installing, uninstalling, enabling, and disabling triggers are table-level
    operations that call ``ALTER`` on the table. This is a global
    operation and will affect all running processing. Do not use these
    methods in application code. If you want to ignore a trigger dynamically
    in an application, using `pgtrigger.ignore`, which is covered in
    the :ref:`ignoring_triggers` section.

There are circumstances when it is undesirable to always install triggers
after migrations, especially when performing complex multi-step migrations
where installing a trigger midway could result in errors.
To turn off creating triggers in migrations, configure the
``PGTRIGGER_INSTALL_ON_MIGRATE`` setting to ``False``.

Triggers can be programmatically configured with the following code:

* `pgtrigger.install`: Install triggers
* `pgtrigger.uninstall`: Uninstall triggers
* `pgtrigger.enable`: Enable triggers
* `pgtrigger.disable`: Disable triggers
* `pgtrigger.prune`: Uninstall triggers created by ``django-pgtrigger``
  that are no longer in the codebase.

Triggers can also be configured with similar management commands.
See the :ref:`commands` section for more details.

.. note::

    If triggers are disabled (as opposed to uninstalled), they have
    to be re-enabled again and will not be re-enabled automatically
    during migrations.



Configuring triggers on external models
---------------------------------------

Triggers can be registered for models that are part of third party apps.
This can be done by manually calling the `pgtrigger.register`
decorator:

.. code-block:: python

    from django.contrib.auth.models import User
    import pgtrigger

    # Register a protection trigger for the User model
    pgtrigger.register(pgtrigger.Protect(...))(User)

.. note::

    Be sure that triggers are registered via an app config's
    ``ready()`` method so that the registration happens!
    More information on this
    `here <https://docs.djangoproject.com/en/3.0/ref/applications/#django.apps.apps.ready>`__.


More trigger examples
~~~~~~~~~~~~~~~~~~~~~

The fun doesn't stop here. There is an entire tutorial repository for
using ``django-pgtrigger`` at
`<https://wesleykendall.github.io/django-pgtrigger-tutorial/>`__.
This tutorial covers many of the examples we've already covered, and it
has interactive code examples you can run locally. Go check it out!

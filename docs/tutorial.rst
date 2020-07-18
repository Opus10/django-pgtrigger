.. _tutorial:

Tutorial
========

Postgres triggers provide the ability to specify database actions
that should occur when operations happen in the database (INSERT, UPDATE,
DELETE, TRUNCATE) on certain conditions of the affected rows.

The `pgtrigger.Trigger` object is the base class for all triggers.
Attributes of this class mirror the syntax required for making a Postgres
trigger, and one has the ability to input the exact
`PL/pgSQL code <https://www.postgresql.org/docs/current/plpgsql.html>`__
that is executed by Postgres in the trigger. ``pgtrigger`` also has several
helper classes, like `pgtrigger.Protect`, that implement some core
triggers you can configure without having to write ``PL/pgSQL``
syntax.

When declaring a trigger, one must provide the following required attributes:

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

* **condition**

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


By default, all triggers are row-level triggers, meaning they fire on
operations to individual rows. One can define statement-level triggers
with the ``level`` attribute. The ``referencing`` attribute is a special
attribute for statement-level triggers:

* **level**

    Declares if the trigger is row (`pgtrigger.Row`) or statement
    level (`pgtrigger.Statement`). Defaults to `pgtrigger.Row`.

* **referencing**

    When constructing a statement-level trigger, allows one to reference
    the ``OLD`` and ``NEW`` rows as transition tables using
    the `pgtrigger.Referencing` construct. For example,
    ``pgtrigger.Referencing(old='old_table_name', new='new_table_name')``
    will make an ``old_table_name`` and ``new_table_name`` table available
    as transition tables in the statement-level trigger. See
    `this <https://dba.stackexchange.com/a/177468>`__ for an additional
    explanation on the referncing construct and read the trigger cookbook
    later for an example.


  .. note::

      The "referencing" construct for statement-level triggers is only available
      in Postgres10 and up.


Installing triggers for models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Similar to the Django admin, ``pgtrigger`` triggers are registered to models
using the `pgtrigger.register` decorator. The decorator takes a variable
amount of `pgtrigger.Trigger` objects that should be installed for the
model.

For example, this trigger definition protects this model from being
deleted:

.. code-block:: python

    from django.db import models
    import pgtrigger


    @pgtrigger.register(
        pgtrigger.Protect(operation=pgtrigger.Delete)
    )
    class CannotDelete(models.Model):
        field = models.CharField(max_length=16)

The triggers are installed automatically when running
``manage.py migrate``. If a trigger definition is removed from the project,
the triggers will be removed in the database. If the trigger
changes, the new one will be created and the old one will be dropped
during migrations.

To turn off creating triggers in migrations, configure the
``PGTRIGGER_INSTALL_ON_MIGRATE`` setting to ``False``.
Triggers can manually be configured with the following code:

* `pgtrigger.install`: Installs all triggers
* `pgtrigger.uninstall`: Uninstalls all triggers
* `pgtrigger.enable`: Enables all triggers
* `pgtrigger.disable`: Disables all triggers

.. note::

    If triggers are disabled (as opposed to uninstalled), they have
    to be re-enabled again and will not be re-enabled automatically
    during migrations.

Trigger cookbook
~~~~~~~~~~~~~~~~

Here are a few more examples of how you can configure triggers
using the utilities in ``pgtrigger``.

Keeping a field in-sync with another
------------------------------------

We can register a `pgtrigger.Trigger` before an update
or insert to ensure that two fields remain in sync.

.. code-block:: python

    import pgtrigger


    @pgtrigger.register(
        pgtrigger.Trigger(
            operation=pgtrigger.Update | pgtrigger.Insert,
            when=pgtrigger.Before,
            func='NEW.in_sync_int = NEW.int_field; RETURN NEW;',
        )
    )
    class MyModel(models.Model):
        int_field = models.IntField()
        in_sync_int = models.IntField(help_text='Stays the same as "int_field"')

.. note::

    When writing a `pgtrigger.Before` trigger, be sure to return the row over
    which the operation should be applied. Returning no row will prevent the
    operation from happening (which can be useful for certain behavior).
    See `the docs here <https://www.postgresql.org/docs/current/plpgsql-trigger.html>`__
    for more information about this behavior.

Soft-delete models
------------------

A soft-delete model is one that sets a field on the model to ``False``
instead of deleting the model from the database. For example, it is
common is set an ``is_active`` field on a model to ``False`` to soft
delete it.

The `pgtrigger.SoftDelete` trigger takes the field as an argument and
sets it to ``False`` whenever a deletion happens on the model. For example:

.. code-block:: python

    import pgtrigger


    @pgtrigger.register(pgtrigger.SoftDelete(field='is_active'))
    class SoftDeleteModel(models.Model):
        # This field is set to false when the model is deleted
        is_active = models.BooleanField(default=True)

    m = SoftDeleteModel.objects.create()
    m.delete()

    # The model will still exist, but it is no longer active
    assert not SoftDeleteModel.objects.get().is_active

The `pgtrigger.SoftDelete` trigger allows one to do soft deletes at the
database level with no instrumentation in code at the application level.
This reduces the possibility for holes in the application that can
accidentally delete the model when not going through the appropriate interface.

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

Create an append-only model using the `pgtrigger.Protect`
utility and registering it for the ``UPDATE`` and ``DELETE`` operations:

.. code-block:: python

    import pgtrigger
    from django.db import models


    @pgtrigger.register(
        pgtrigger.Protect(
            operation=(pgtrigger.Update | pgtrigger.Delete)
        )
    )
    class AppendOnlyModel(models.Model):
        my_field = models.IntField()

.. note::

    This table can still be truncated, although this is not an operation
    supported by Django. One can still protect against this by adding the
    `pgtrigger.Truncate` operation.


Dynamic deletion protection
---------------------------

Only allow models with a ``deletable`` flag to be deleted:

.. code-block:: python

    import pgtrigger
    from django.db import models


    @pgtrigger.register(
        pgtrigger.Protect(
            operation=pgtrigger.Delete,
            condition=pgtrigger.Q(old__is_deletable=False)
        )
    )
    class DynamicDeletionModel(models.Model):
        is_deletable = models.BooleanField(default=False)


Redundant update protection
---------------------------

Want to error every time someone tries to update a
row with the exact same values? Here's how:

.. code-block:: python

    import pgtrigger
    from django.db import models


    @pgtrigger.register(
        pgtrigger.Protect(
            operation=pgtrigger.Delete,
            condition=pgtrigger.Condition(
                'OLD.* IS NOT DISTINCT FROM NEW.*'
            )
        )
    )
    class RedundantUpdateModel(models.Model):
        redundant_field1 = models.BooleanField(default=False)
        redundant_field2 = models.BooleanField(default=False)


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


Statement-level triggers and transition tables
----------------------------------------------

Most of the terminology and examples around Postgres triggers have been
centered around "row-level" triggers, i.e. triggers that fire on events
for every row. However, row-level triggers can be expensive in some
circumstances. For example, imagine we are doing a bulk Django update
over a table with 10,000 rows:

.. code-block:: python

    MyLargeModel.objects.update(is_active=False)

If we had any row-level triggers configured for ``MyLargeModel``, they
would fire 10,000 times for every updated row even though the query above
is only issuing one single update statement.

Although triggers are issued at the database level and will not induce
expensive round trips to the database, it can still be unnecessarily expensive
to do row-level triggers for certain situations.

Statement-level triggers, in contrast to row-level triggers, are executed
once per statement. One only needs to provide ``level=pgtrigger.Statement`` to
the trigger to configure this. However,
keep in mind that trigger conditions and are largely not applicable to
statement-level triggers since the ``OLD`` and ``NEW`` row variables are
always ``NULL``.

Postgres10 introduced the notion of "transition tables"
to allow users to access old and new rows in a statement-level trigger
(see `this <https://dba.stackexchange.com/a/177468>`__ for an example).
One can use the `pgtrigger.Referencing` construct to write a statement-level trigger
that references the old and new rows.

For example, imagine we have a log model that logs changes to a table
and keeps track of an old field and new field for every update.
We can create a statement-level trigger that logs the old and new
fields from a transition table to this persisted log model like so:

.. code-block:: python

    from django.db import models
    import pgtrigger


    class LogModel(models.Model):
        old_field = models.CharField(max_length=32)
        new_field = models.CharField(max_length=32)


    @pgtrigger.register(
        pgtrigger.Trigger(
            level=pgtrigger.Statement,
            when=pgtrigger.After,
            operation=pgtrigger.Update,
            referencing=pgtrigger.Referencing(old='old_values', new='new_values'),
            func=f'''
                INSERT INTO {LogModel._meta.db_table}(level, old_field, new_field)
                SELECT
                    'STATEMENT' AS level,
                    old_values.field AS old_field,
                    new_values.field AS new_field
                FROM old_values
                    JOIN new_values ON old_values.id = new_values.id;
                RETURN NULL;
            ''',
        )
    )
    class LoggedModel(models.Model):
        field = models.CharField(max_length=32)


With this trigger definition, we'll now have the following happen with only
one additional query in the trigger:

.. code-block:: python

    LoggedModel.objects.bulk_create([LoggedModel(field='old'), LoggedModel(field='old')])

    # Update all fields to "new"
    LoggedModel.objects.update(field='new')

    # The trigger should have persisted these updates
    print(LogModel.values('old_field', 'new_field'))

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

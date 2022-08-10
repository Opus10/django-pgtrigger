.. _basics:

Basics
======

The anatomy of a trigger
~~~~~~~~~~~~~~~~~~~~~~~~

Postgres triggers are database functions written in PL/pgSQL that execute based on events
and conditions.

The `pgtrigger.Trigger` object is the base class for all triggers in ``django-pgtrigger``.
Its attributes mirror the syntax required for
`making a Postgres trigger <https://www.postgresql.org/docs/current/sql-createtrigger.html>`__.
Here are the most common attributes you'll use:

* **name**

    The identifying name of trigger. Is unique for every model and must
    be less than 48 characters.

* **operation**

    The table operation that fires a trigger. Operations are `pgtrigger.Update`,
    `pgtrigger.Insert`, `pgtrigger.Delete`,
    `pgtrigger.Truncate`, or `pgtrigger.UpdateOf`.
    They can be ``OR`` ed
    together (e.g.  ``pgtrigger.Insert | pgtrigger.Update``)
    to configure triggers on a combination of operations.

    .. note::

        `pgtrigger.UpdateOf` fires when columns appear in an ``UPDATE``
        statement. It will not fire if other triggers update the columns.
        See the notes in the
        `Postgres docs <https://www.postgresql.org/docs/12/sql-createtrigger.html>`__
        for more information.

    .. note::

        Some conditions cannot be combined. For
        example, `pgtrigger.UpdateOf` cannot be combined with other
        operations.

* **when**

    When the trigger should run in relation to the operation.
    `pgtrigger.Before` executes the trigger before the operation, and
    vice versa for `pgtrigger.After`. `pgtrigger.InsteadOf` is used for SQL views.

    .. note::

        `pgtrigger.Before` and `pgtrigger.After` can be used on SQL views
        under some circumstances. See
        `the Postgres docs <https://www.postgresql.org/docs/12/sql-createtrigger.html>`__
        for a breakdown.

* **condition** *(optional)*

    Conditionally execute the trigger based on the ``OLD``
    or ``NEW`` rows.

    `pgtrigger.Condition` objects accept `pgtrigger.Q` and `pgtrigger.F`
    objects for constructing ``WHERE`` clauses with the ``OLD`` and ``NEW`` rows.
    Conditions can also be created from raw SQL. See the :ref:`cookbook` for
    more examples.

    .. note::

        Be sure to familiarize yourself with ``OLD`` and ``NEW`` rows when
        writing conditions by consulting the `Postgres docs <https://www.postgresql.org/docs/current/plpgsql-trigger.html>`__.
        For example, ``OLD`` is always ``NULL`` in `pgtrigger.Insert` triggers.

Here are attributes you'll need when writing more complex
triggers.

* **func**

    The raw PL/pgSQL function that is executed.

    .. note::

        This is *not* the entire declared trigger function, but rather
        the snippet of PL/pgSQL that is nested in the
        ```DECLARE ... BEGIN ... END``` portion of the trigger.

* **declare** *(optional)*

    Define additional variable declarations as a list of ``(variable_name, variable_type)`` tuples.
    For example ``declare=[('my_var_1', 'BOOLEAN'), ('my_var_2', 'JSONB')]``.

* **level** *(optional, default=pgtrigger.Row)*

    Configures the trigger to fire once for every row (`pgtrigger.Row`) or once for
    every statement (`pgtrigger.Statement`).

* **referencing** *(optional)*

    References the ``OLD`` and ``NEW`` rows as transition tables in statement-level triggers.
    For example, ``pgtrigger.Referencing(old='old_table_name', new='new_table_name')``
    will make an ``old_table_name`` and ``new_table_name`` table available
    as transition tables. See
    `this StackExchange answer <https://dba.stackexchange.com/a/177468>`__ for additional
    details, and see the :ref:`cookbook` for an example.

    .. note::

        The ``REFERENCING`` construct for statement-level triggers is only available
        in Postgres 10 and up.

* **timing** *(optional)*

    Create a deferrable ``CONSTRAINT`` trigger when set. Use `pgtrigger.Immediate` to
    execute the trigger at the end of a statement and `pgtrigger.Deferred` to execute it
    at the end of a transaction.

    .. note::

        Deferrable triggers must have the ``level`` set to `pgtrigger.Row` and ``when``
        set to `pgtrigger.After`.


Defining and installing triggers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Triggers are defined in the ``triggers`` attribute of the model ``Meta``
class. For example, this trigger protects the model from being
deleted:

.. code-block:: python

    from django.db import models
    import pgtrigger


    class CannotDelete(models.Model):
        class Meta:
            triggers = [
                pgtrigger.Protect(name='protect_deletes', operation=pgtrigger.Delete)
            ]

Triggers are installed by first running ``python manage.py makemigrations`` and then ``python manage.py migrate``.

If you'd like to install a trigger on a model of a third-party app, see the 
:ref:`advanced_installation` section. This section also covers how you can manually install,
enable, and disable triggers globally.
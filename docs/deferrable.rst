.. _deferrable:

Deferrable Triggers
===================

Triggers are "deferrable" if their execution can be postponed until the end of
the transaction. This behavior can be desirable for certain situations.

For example, here we ensure a ``Profile`` model always exists for every ``User``:

.. code-block:: python

    class Profile(models.Model):
        user = models.OneToOneField(User, on_delete=models.CASCADE)


    class UserProxy(User):
        class Meta:
            proxy = True
            triggers = [
                pgtrigger.Trigger(
                    name="profile_for_every_user",
                    when=pgtrigger.After,
                    operation=pgtrigger.Insert,
                    timing=pgtrigger.Deferred,
                    func=f"""
                        IF NOT EXISTS (SELECT FROM {Profile._meta.db_table} WHERE user_id = NEW.id) THEN
                            RAISE EXCEPTION 'Profile does not exist for user %', NEW.id;
                        END IF;
                        RETURN NEW;
                    """
                )
            ]

This trigger ensures that any creation of a ``User`` will fail if a ``Profile`` does not exist. Note that we must create
them both in a transaction:

.. code-block::

    # This will succeed since the user has a profile when
    # the transaction completes
    with transaction.atomic():
        user = User.objects.create()
        Profile.objects.create(user=user)

    # This will fail since it is not in a transaction
    user = User.objects.create()
    Profile.objects.create(user=user)


Ignoring deferrable triggers
----------------------------

Deferrable triggers can be ignored, but remember that they execute at the very end of a transaction. If
`pgtrigger.ignore` does not wrap the transaction, the deferrable trigger will not be ignored.

Here is a correct way of ignoring the deferrable trigger from the initial example:

.. code-block:: python

    with pgtrigger.ignore("my_app.UserProxy:profile_for_every_user"):
        # Use durable=True, otherwise we may be wrapped in a parent
        # transaction
        with transaction.atomic(durable=True):
            # We no longer need a profile for a user...
            User.objects.create(...)

Here's an example of code that will fail:

.. code-block:: python

    with transaction.atomic():
        # This ignore does nothing for this trigger. ``pgtrigger.ignore`` will no longer
        # be in effect by the time the trigger runs at the end of the transaction.
        with pgtrigger.ignore("my_app.UserProxy:profile_for_every_user"):
            # The trigger will raise an exception
            User.objects.create(...)


Adjusting runtime behavior
--------------------------

When a deferrable trigger is declared, the ``timing`` attribute can be adjusted at runtime
using `pgtrigger.constraints`. This function mimics Postgres's ``SET CONSTRAINTS``
statement. Check `the Postgres docs for more info <https://www.postgresql.org/docs/current/sql-set-constraints.html>`__.

`pgtrigger.constraints` takes the new timing value and a list of trigger URIs over which
to apply the value. The value is in effect until the end of the transaction.

Let's take our original example. We can set the trigger to immediately run, causing it to
throw an error:

.. code-block:: python

    with transaction.atomic():
        user = User.objects.create(...)

        # Make the deferrable trigger fire immediately. This will cause an exception
        # because a profile has not yet been created for the user
        pgtrigger.constraints(pgtrigger.Immediate, "auth.User:profile_for_every_user")


Keep in mind that the constraint settings stay in effect until the end of the
transaction. If a parent transaction wraps our code, timing overrides will persist.

.. tip::

    You can do the opposite of our example, creating triggers with
    ``timing=pgtrigger.Immediate`` and deferring their execution dynamically.

.. note::

    In a multi-schema setup, only triggers in the schema search path will be
    overridden with `pgtrigger.constraints`.
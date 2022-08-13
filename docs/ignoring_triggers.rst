.. _ignoring_triggers:

Ignoring Execution
==================

`pgtrigger.ignore` is a decorator and context manager that temporarily ignores triggers for a single
thread of execution. Here we ignore deletion protection:

.. code-block:: python

    class CannotDelete(models.Model):
        class Meta:
            triggers = [
                pgtrigger.Protect(name="protect_deletes", operation=pgtrigger.Delete)
            ]


    # Bypass deletion protection
    with pgtrigger.ignore("my_app.CannotDelete:protect_deletes"):
        CannotDelete.objects.all().delete()

As shown above, `pgtrigger.ignore` takes a trigger URI that is formatted as
``{app_label}.{model_name}:{trigger_name}``. Multiple trigger URIs can
be given to `pgtrigger.ignore`, and `pgtrigger.ignore` can be nested.
If no trigger URIs are provided to `pgtrigger.ignore`, all triggers are ignored.

.. tip::

    See all trigger URIs with ``python manage.py pgtrigger ls``

By default, `pgtrigger.ignore` configures ignoring triggers on every postgres database.
This can be changed with the ``databases`` argument.

.. important::

    Remember, `pgtrigger.ignore` ignores the execution of a trigger on a per-thread basis.
    This is very different from disabling a trigger or uninstalling a trigger globally.
    See the :ref:`advanced_installation` section for more details on managing the installation
    of triggers.

Transaction notes
-----------------

`pgtrigger.ignore` flushes a temporary Postgres variable at the end of the context manager
if running in a transaction. This could cause issues for transactions that are in an errored state.

Here's an example of when this case happens:

.. code-block:: python

    with transaction.atomic():
        with ptrigger.ignore("app.Model:protect_inserts"):
            try:
                # Create an object that raises an integrity error
                app.Model.objects.create(unique_key="duplicate")
            except IntegrityError:
                # Ignore the integrity error
                pass

        # When we exit the context manager here, it will try to flush
        # a local Postgres variable. This causes an error because the transaction
        # is in an errored state.

If you're ignoring triggers and handling database errors, there are two ways
to prevent this error from happening:

1. Wrap the outer transaction in ``with pgtrigger.ignore.session():`` so that
   the session is completed outside the transaction.
2. Wrap the inner ``try/except`` in ``with transaction.atomic():`` so that
   the errored part of the transaction is rolled back before the `pgtrigger.ignore`
   context manager ends.

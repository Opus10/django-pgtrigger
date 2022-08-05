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

Run ``python manage.py pgtrigger ls`` to see the URIs of all triggers.

.. note::

    Remember, `pgtrigger.ignore` ignores the execution of a trigger on a per-thread basis.
    This is very different from disabling a trigger or uninstalling a trigger globally.
    See the :ref:`advanced_installation` section for more details on managing the installation
    of triggers.

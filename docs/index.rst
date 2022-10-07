django-pgtrigger
================

``django-pgtrigger`` helps you write
`Postgres triggers <https://www.postgresql.org/docs/current/sql-createtrigger.html>`__
for your Django models.

Why should I use triggers?
~~~~~~~~~~~~~~~~~~~~~~~~~~

Triggers can solve a variety of complex problems more reliably, performantly, and succinctly than application code.
For example,

* Protecting operations on rows or columns (`pgtrigger.Protect`).
* Making read-only models or fields (`pgtrigger.ReadOnly`).
* Soft-deleting models (`pgtrigger.SoftDelete`).
* Snapshotting and tracking model changes (`django-pghistory <https://django-pghistory.readthedocs.io>`__).
* Enforcing field transitions (`pgtrigger.FSM`).
* Keeping a search vector updated for full-text search (`pgtrigger.UpdateSearchVector`).
* Building official interfaces
  (e.g. enforcing use of ``User.objects.create_user`` and not
  ``User.objects.create``).
* Versioning models, mirroring fields, computing unique model hashes, and the list goes on...

All of these examples require no overridden methods, no base models, and no signal handling.

Quick start
~~~~~~~~~~~

Install ``django-pgtrigger`` with ``pip3 install django-pgtrigger`` and
add ``pgtrigger`` to ``settings.INSTALLED_APPS``.

``pgtrigger.Trigger`` objects are added to ``triggers`` in model
``Meta``. ``django-pgtrigger`` comes with several trigger classes,
such as ``pgtrigger.Protect``. In the following, we're protecting
the model from being deleted:

.. code-block:: python

    class ProtectedModel(models.Model):
        """This model cannot be deleted!"""

        class Meta:
            triggers = [
                pgtrigger.Protect(name='protect_deletes', operation=pgtrigger.Delete)
            ]

When migrations are created and executed, ``ProtectedModel`` will raise an
exception anytime a deletion is attempted.

Let's extend this example further and only protect deletions on inactive objects.
In this example, the trigger conditionally runs when the row being deleted
(the ``OLD`` row in trigger terminology) is still active:

.. code-block:: python

    class ProtectedModel(models.Model):
        """Active object cannot be deleted!"""
        is_active = models.BooleanField(default=True)

        class Meta:
            triggers = [
                pgtrigger.Protect(
                    name='protect_deletes',
                    operation=pgtrigger.Delete,
                    condition=pgtrigger.Q(old__is_active=True)
                )
            ]


``django-pgtrigger`` uses ``pgtrigger.Q`` and ``pgtrigger.F`` objects to
conditionally execute triggers based on the ``OLD`` and ``NEW`` rows.
Combining these Django idioms with ``pgtrigger.Trigger`` objects
can solve a wide variety of problems without ever writing SQL. Users,
however, can still use raw SQL for complex cases.

Triggers are installed like other database objects. Run
``python manage.py makemigrations`` and ``python manage.py migrate`` to install triggers.

Compatibility
~~~~~~~~~~~~~

``django-pgtrigger`` is compatible with Python 3.7 -- 3.10, Django 2.2 -- 4.1, and Postgres 10 -- 14.

Next steps
~~~~~~~~~~

We recommend everyone first read:

* :ref:`installation` for how to install the library.
* :ref:`basics` for an overview and motivation.

After this, there are several usage guides:

* :ref:`cookbook` for trigger examples.
* :ref:`ignoring_triggers` for dynamically ignoring triggers.
* :ref:`deferrable` for deferring trigger execution.
* :ref:`advanced_installation` for installing triggers on third-party models, many-to-many models, programmatic installation, and more.
* :ref:`advanced_db` for notes on how triggers work in multi-database, mutli-schema, or partitioned database setups.

There's additional help in these sections:

* :ref:`faq` for common questions like testing and disabling triggers.
* :ref:`troubleshooting` for advice on known issues.
* :ref:`upgrading` for upgrading to new major versions.
* :ref:`further_reading` for additional reading and videos.

Finally, core API information exists in these sections:

* :ref:`settings` for all available Django settings.
* :ref:`commands` for using the ``python manage.py pgtrigger`` management commands.
* :ref:`module` for documentation of the ``pgtrigger`` module.
* :ref:`release_notes` for information about every release.
* :ref:`contributing` for details on contributing to the codebase.

django-pgtrigger
################

``django-pgtrigger`` helps you write
`Postgres triggers <https://www.postgresql.org/docs/current/sql-createtrigger.html>`__
for your Django models.

Why should I use triggers?
==========================

Triggers can solve a variety of complex problems more reliably, performantly, and succinctly than application code.
For example,

1. Protecting operations on rows or columns (``pgtrigger.Protect``).
2. Soft-deleting models (``pgtrigger.SoftDelete``).
3. Snapshotting and tracking model changes (`django-pghistory <https://django-pghistory.readthedocs.io/>`__).
4. Enforcing field transitions (``pgtrigger.FSM``).
5. Keeping a search vector updated for full-text search (``pgtrigger.UpdateSearchVector``).
6. Building official interfaces
   (e.g. enforcing use of ``User.objects.create_user`` and not
   ``User.objects.create``).
7. Versioning models, mirroring fields, computing unique model hashes, and the list goes on...

All of these examples require no overridden methods, no base models, and no signal handling.

Quick start
===========

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
                pgtrigger.Protect(name="protect_deletes", operation=pgtrigger.Delete)
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
                    name="protect_deletes",
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

If triggers are new to you, don't worry.
The `pgtrigger docs <https://django-pgtrigger.readthedocs.io/>`__ cover triggers in
more detail and provide many examples.

Compatibility
=============

``django-pgtrigger`` is compatible with Python 3.7 - 3.10, Django 2.2 - 4.1, and Postgres 10 - 14.

Documentation
=============

`View the pgtrigger docs here <https://django-pgtrigger.readthedocs.io/>`__ to
learn more about:

* Trigger basics and motivation for using triggers.
* How to use the built-in triggers and how to build custom ones.
* Installing triggers on third-party models, many-to-many fields, and other
  advanced scenarios.
* Ignoring triggers dynamically and deferring trigger execution.
* Multiple database, schema, and partitioning support.
* Frequently asked questions, common issues, and upgrading.
* The commands, settings, and module.

Installation
============

Install django-pgtrigger with::

    pip3 install django-pgtrigger

After this, add ``pgtrigger`` to the ``INSTALLED_APPS``
setting of your Django project.

Other Material
==============

After you've read the docs, check out
`this tutorial <https://wesleykendall.github.io/django-pgtrigger-tutorial/>`__
with interactive examples from a Django meetup talk.

The `DjangoCon 2021 talk <https://www.youtube.com/watch?v=Tte3d4JjxCk>`__
also breaks down triggers and shows several examples.

Contributing Guide
==================

For information on setting up django-pgtrigger for development and
contributing changes, view `CONTRIBUTING.rst <CONTRIBUTING.rst>`_.

Primary Authors
===============

- @wesleykendall (Wes Kendall, wesleykendall@protonmail.com)

Other Contributors
==================

- @jzmiller1
- @rrauenza
- @ralokt

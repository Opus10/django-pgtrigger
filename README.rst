django-pgtrigger
################

``django-pgtrigger`` provides primitives for configuring
`Postgres triggers <https://www.postgresql.org/docs/current/sql-createtrigger.html>`__
on Django models.

Triggers can solve a
wide variety of database-level problems more elegantly and reliably
than in the application-level of Django. Here are some common
problems that can be solved with triggers, many of which we later show how to
solve in the docs:

1. Protecting updates and deletes or rows or columns (``pgtrigger.Protect``).
2. Soft deleting models by setting a field to a value on delete (``pgtrigger.SoftDelete``).
3. Tracking changes to models or columns change, or when specific conditions
   happen (`django-pghistory <https://django-pghistory.readthedocs.io>`__ uses ``django-pgtrigger`` to do this).
4. Keeping fields in sync with other fields.
5. Ensuring that engineers use an official interface
   (e.g. engineers must use ``User.objects.create_user`` and not
   ``User.objects.create``).
6. Only allowing a status field of a model to transition through certain
   states (``pgtrigger.FSM``).

Quick Start
===========

Install ``django-pgtrigger`` with ``pip install django-pgtrigger`` and
add ``pgtrigger`` to ``settings.INSTALLED_APPS``.

Models are decorated with ``@pgtrigger.register`` and supplied with
``pgtrigger.Trigger`` objects. If you don't have access to the model definition,
you can still call ``pgtrigger.register`` programmatically.

Users declare the plpgsql code manually
in a ``pgtrigger.Trigger`` object or can use the derived triggers in
``django-pgtrigger`` that implement common scenarios. For example,
``pgtrigger.Protect`` can protect operations on a model, such as deletions:

.. code-block:: python

    from django.db import models
    import pgtrigger


    @pgtrigger.register(pgtrigger.Protect(operation=pgtrigger.Delete))
    class CannotBeDeletedModel(models.Model):
        """This model cannot be deleted!"""

``django-pgtrigger`` aims to alleviate the boilerplate of triggers and
having to write raw SQL by using common Django idioms. For example, users
can use ``pgtrigger.Q`` and ``pgtrigger.F`` objects to
conditionally execute triggers based on the ``OLD`` and ``NEW`` row
being modified. For example, let's only protect deletes
against "active" rows of a model:

.. code-block:: python

    from django.db import models
    import pgtrigger


    @pgtrigger.register(
        pgtrigger.Protect(
            operation=pgtrigger.Delete,
            # Protect deletes when the OLD row of the trigger is still active
            condition=pgtrigger.Q(old__is_active=True)
        )
    )
    class CannotBeDeletedModel(models.Model):
        """Active model object cannot be deleted!"""
        is_active = models.BooleanField(default=True)


Combining ``pgtrigger.Q``, ``pgtrigger.F``, and derived ``pgtrigger.Trigger``
objects can solve a wide array of Django problems without ever having to
write raw SQL. Users, however, can still customize
triggers and write as much raw SQL as needed for their use case.


Tutorial
========

For a complete run-through of ``django-pgtrigger`` and all derived
triggers (along with a trigger cookbook!), read the
`pgtrigger docs <https://django-pgtrigger.readthedocs.io/>`__. The docs
have a full tutorial of how to configure triggers and lots of code examples.

After you have gone through the
tutorial in the docs, check out
`<https://wesleykendall.github.io/django-pgtrigger-tutorial/>`__, which
is an interactive tutorial written for a Django meetup talk about
``django-pgtrigger``.


Documentation
=============

`View the django-pgtrigger docs here
<https://django-pgtrigger.readthedocs.io/>`_.

Installation
============

Install django-pgtrigger with::

    pip3 install django-pgtrigger

After this, add ``pgtrigger`` to the ``INSTALLED_APPS``
setting of your Django project.

Contributing Guide
==================

For information on setting up django-pgtrigger for development and
contributing changes, view `CONTRIBUTING.rst <CONTRIBUTING.rst>`_.

Primary Authors
===============

- @wesleykendall (Wes Kendall)

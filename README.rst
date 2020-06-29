django-pgtrigger
################

``django-pgtrigger`` provides primitives for configuring
`Postgres triggers <https://www.postgresql.org/docs/current/sql-createtrigger.html>`__
on Django models.

Models can be decorated with `pgtrigger.register` and supplied with
`pgtrigger.Trigger` objects. These will automatically be installed after
migrations. Users can use Django idioms such as ``Q`` and ``F`` objects to
declare trigger conditions, alleviating the need to write raw SQL for a large
amount of use cases.

``django-pgtrigger`` comes built with some derived triggers for expressing
common patterns. For example, ``pgtrigger.Protect`` can protect operations
on a model, such as deletions or updates (e.g. an append-only model). The
``pgtrigger.Protect`` trigger can even target protecting operations on
specific updates of fields (e.g. don't allow updates if ``is_active`` is
``False`` on a model). Another derived trigger, ``pgtrigger.SoftDelete``,
can soft-delete models by setting a field to ``False`` when a deletion
happens on the model.

Read the `pgtrigger docs <https://django-pgtrigger.readthedocs.io/>`__ for
examples of how to use triggers in your application.


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

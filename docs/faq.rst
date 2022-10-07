.. _faq:

Frequently Asked Questions
==========================

Triggers are scary, don't you think?
------------------------------------

Enforcing data integrity in application code is what you should be afraid of. Triggers, like uniqueness constraints,
are a blessing that help solidify your data modeling.

The best way to ensure triggers are behaving correctly is to:

1. Write tests for them.
2. Run ``python manage.py pgtrigger ls`` to verify they are installed in production.

Why not implement logic with signals or model methods?
------------------------------------------------------

See :ref:`advantages_of_triggers`

Why can't I join foreign keys in conditions?
---------------------------------------------

Postgres only allows columns of the changed rows to be used in trigger conditions, and data cannot
be joined. That's why, for example, one cannot write a condition like ``Q(old__foreign_key__field="value")``.

Conditional logic like this must be performed in the trigger function itself by manually joining
data.

How do I test triggers?
-----------------------

Manipulate your models in your test suite and verify the expected result happens.


If you've turned off migrations for your test suite, call `pgtrigger.install` after the database is set up or set ``settings.PGTRIGGER_INSTALL_ON_MIGRATE`` to ``True`` to ensure triggers are installed for your tests.

.. warning::

    Be sure the ``settings.PGTRIGGER_INSTALL_ON_MIGRATE`` setting is isolated to your test suite, otherwise it could
    cause unexpected problems in production when reversing migrations.

When a failure-based trigger like `pgtrigger.Protect` fails, a ``django.db.utils.InternalError`` is raised and
can be caught in your test function. Keep in mind that this will place the current transaction in an errored
state. If you'd like to test triggers like this without needing to use a transaction test case, wrap the
assertion in ``transaction.atomic``. This is illustrated below with pseudocode using 
`pytest-django <https://pytest-django.readthedocs.io/en/latest/>`__.

.. code-block::

    from djagno.db import transaction
    from django.db.utils import InternalError
    import pytest

    @pytest.mark.django_db
    def test_protection_trigger():
        with pytest.raises(InternalError, match="Cannot delete"), transaction.atomic():
            # Try to delete protected model

        # Since the above assertion is wrapped in transaction.atomic, we will still have
        # a valid transaction in our test case here

How do I disable triggers?
--------------------------

Use `pgtrigger.ignore` if you need to temporarily ignore triggers in your application (see :ref:`ignoring_triggers`). Only use the core installation commands if you want to disable or uninstall triggers globally (see the :ref:`commands` section). **Never** run the core
installation commands in application code.

How can I reference the table name in a custom function?
--------------------------------------------------------

When writing a trigger in ``Meta``, it's not possible to access other model meta properties like ``db_table``.
Use `pgtrigger.Func` to get around this. See :ref:`func_model_properties`.

How can I contact the author?
-----------------------------

The primary author, Wes Kendall, loves to talk to users. Message him at `wesleykendall@protonmail.com <mailto:wesleykendall@protonmail.com>`__ for any feedback. Any questions, feature requests, or bugs should
be reported as `issues here <https://github.com/Opus10/django-pgtrigger/issues>`__.

Wes and other `Opus 10 engineers <https://opus10.dev>`__ do contracting work, so keep them in mind if your company
uses Django.

# Frequently Asked Questions

## Triggers are scary, don't you think?

Enforcing data integrity in application code is what you should be afraid of. Triggers, like uniqueness constraints, are a blessing that help solidify your data modeling.

The best way to ensure triggers are behaving correctly is to:

1. Write tests for them.
2. Run `python manage.py pgtrigger ls` to verify they are installed in production.

## Why not implement logic with signals or model methods?

See [this section from the docs](basics.md#advantages_of_triggers)

## Why can't I join foreign keys in conditions?

Postgres only allows columns of the changed rows to be used in trigger conditions, and data cannot be joined. That's why, for example, one cannot write a condition like `Q(old__foreign_key__field="value")`.

Conditional logic like this must be performed in the trigger function itself by manually joining data.

## How do I test triggers?

Manipulate your models in your test suite and verify the expected result happens.

If you've turned off migrations for your test suite, call [pgtrigger.install][] after the database is set up or set `settings.PGTRIGGER_INSTALL_ON_MIGRATE` to `True` to ensure triggers are installed for your tests.

!!! warning

    Be sure the `settings.PGTRIGGER_INSTALL_ON_MIGRATE` setting is isolated to your test suite, otherwise it could cause unexpected problems in production when reversing migrations.

When a failure-based trigger like [pgtrigger.Protect][] fails, a `django.db.utils.InternalError` is raised and can be caught in your test function. Keep in mind that this will place the current transaction in an errored state. If you'd like to test triggers like this without needing to use a transaction test case, wrap the assertion in `transaction.atomic`. This is illustrated below with pseudocode using [pytest-django](https://pytest-django.readthedocs.io/en/latest/).

```python
from djagno.db import transaction
from django.db.utils import InternalError
import pytest

@pytest.mark.django_db
def test_protection_trigger():
    with pytest.raises(InternalError, match="Cannot delete"), transaction.atomic():
        # Try to delete protected model

    # Since the above assertion is wrapped in transaction.atomic, we will still
    # have a valid transaction in our test case here
```

## How do I disable triggers?

Use [pgtrigger.ignore][] if you need to temporarily ignore triggers in your application (see [Ignoring Execution](ignoring_triggers.md)). Only use the core installation commands if you want to disable or uninstall triggers globally across the **entire application** (see the [Commands](commands.md) section).

## How can I reference the table name in a custom function?

When writing a trigger in `Meta`, it's not possible to access other model meta properties like `db_table`. Use [pgtrigger.Func][] to get around this. See [this example from the cookbook](cookbook.md#func_model_properties).

## How can I report issues or request features

Open a [discussion](https://github.com/Opus10/django-pgtrigger/discussions) for a feature request. You're welcome to pair this with a pull request, but it's best to open a discussion first if the feature request is not trivial.

For bugs, open an [issue](https://github.com/Opus10/django-pgtrigger/issues).

## How can I support the author?

By sponsoring [Wes Kendall](https://github.com/sponsors/wesleykendall). Even the smallest sponsorships are a nice motivation to maintain and enhance Opus10 libraries like django-pgtrigger.

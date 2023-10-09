# django-pgtrigger

`django-pgtrigger` helps you write [Postgres triggers](https://www.postgresql.org/docs/current/sql-createtrigger.html) for your Django models.

## Why should I use triggers?

Triggers can solve a variety of complex problems more reliably, performantly, and succinctly than application code. For example,

* Protecting operations on rows or columns ([pgtrigger.Protect][]).
* Making read-only models or fields ([pgtrigger.ReadOnly][]).
* Soft-deleting models ([pgtrigger.SoftDelete][]).
* Snapshotting and tracking model changes ([django-pghistory](https://django-pghistory.readthedocs.io)).
* Enforcing field transitions ([pgtrigger.FSM][]).
* Keeping a search vector updated for full-text search ([pgtrigger.UpdateSearchVector][]).
* Building official interfaces (e.g. enforcing use of `User.objects.create_user` and not `User.objects.create`).
* Versioning models, mirroring fields, computing unique model hashes, and the list goes on...

All of these examples require no overridden methods, no base models, and no signal handling.

## Quick start

Install `django-pgtrigger` with `pip3 install django-pgtrigger` and add `pgtrigger` to `settings.INSTALLED_APPS`.

[pgtrigger.Trigger][] objects are added to `triggers` in model `Meta`. `django-pgtrigger` comes with several trigger classes, such as [pgtrigger.Protect][]. In the following, we're protecting the model from being deleted:

```python
class ProtectedModel(models.Model):
    """This model cannot be deleted!"""

    class Meta:
        triggers = [
            pgtrigger.Protect(name='protect_deletes', operation=pgtrigger.Delete)
        ]
```

When migrations are created and executed, `ProtectedModel` will raise an exception anytime a deletion is attempted.

Let's extend this example further and only protect deletions on inactive objects. In this example, the trigger conditionally runs when the row being deleted (the `OLD` row in trigger terminology) is still active:

```python
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
```

`django-pgtrigger` uses [pgtrigger.Q][] and [pgtrigger.F][] objects to conditionally execute triggers based on the `OLD` and `NEW` rows. Combining these Django idioms with [pgtrigger.Trigger][] objects can solve a wide variety of problems without ever writing SQL. Users, however, can still use raw SQL for complex cases.

Triggers are installed like other database objects. Run `python manage.py makemigrations` and `python manage.py migrate` to install triggers.

## Compatibility

`django-pgtrigger` is compatible with Python 3.8 - 3.12, Django 3.2 - 4.2, Psycopg 2 - 3, and Postgres 12 - 16.

## Next steps

We recommend everyone first read:

* [Installation](installation.md) for how to install the library.
* [Basics](basics.md) for an overview and motivation.

After this, there are several usage guides:

* [Cookbook](cookbook.md) for trigger examples.
* [Ignoring Execution](ignoring_triggers.md) for dynamically ignoring triggers.
* [Deferrable Triggers](deferrable.md) for deferring trigger execution.
* [Advanced Installation](advanced_installation.md) for installing triggers on third-party models, many-to-many models, programmatic installation, and more.
* [Advanced Database Setups](advanced_db.md) for notes on how triggers work in multi-database, mutli-schema, or partitioned database setups.

There's additional help in these sections:

* [FAQ](faq.md) for common questions like testing and disabling triggers.
* [Troubleshooting](troubleshooting.md) for advice on known issues.
* [Upgrading](upgrading.md) for upgrading to new major versions.
* [Further Reading](further_reading.md) for additional reading and videos.

Finally, core API information exists in these sections:

* [Settings](settings.md) for all available Django settings.
* [Commands](commands.md) for using the `python manage.py pgtrigger` management commands.
* [Module](module.md) for documentation of the `pgtrigger` module.
* [Release Notes](release_notes.md) for information about every release.
* [Contributing Guide](contributing.md) for details on contributing to the codebase.

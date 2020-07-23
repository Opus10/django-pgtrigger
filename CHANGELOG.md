# Changelog
## 1.2.0 (2020-07-22)
### Feature
  - Added ``pgtrigger.ignore`` for dynamically ignoring triggers. [Wes Kendall, b3557bb]

    ``pgtrigger.ignore`` can be used to ignore triggers per thread of
    execution. Docs were updated with examples of how to use
    ``pgtrigger.ignore`` and how to utilize it to create
    "official" interfaces.
  - Allow custom naming of triggers [Wes Kendall, 864d653]

    Triggers can be given a "name" attribute that is used when generating
    the trigger and obtaining it from the registry. This will not only
    make trigger management in the future easier, but it will also make
    it possible to dynamically ignore specific triggers registered to
    models.

## 1.1.0 (2020-07-21)
### Feature
  - Added "Referencing" construct for statement-level triggers. [Wes Kendall, 20d958e]

    The ``pgtrigger.Referencing`` construct allows one to reference
    transition tables in statement-level triggers.
  - Added statement-level triggers. [Wes Kendall, c0cc365]

    django-pgtrigger now has a "level" construct for specifying
    row and statement-level triggers. All triggers default to being
    row-level triggers.
### Trivial
  - Support the "INSTEAD OF" construct for views on SQL triggers. [Wes Kendall, 79f9d54]
  - Updated docs and added a quick start section [Wes Kendall, 9ce7b29]

## 1.0.1 (2020-06-29)
### Trivial
  - Updated README and updated with the latest public django app template. [Wes Kendall, 001ef68]

## 1.0.0 (2020-06-27)
### Api-Break
  - Initial release of django-pgtrigger. [Wes Kendall, 1f737f0]

    ``django-pgtrigger`` provides primitives for configuring
    `Postgres triggers <https://www.postgresql.org/docs/current/sql-createtrigger.html>`__
    on Django models.

    Models can be decorated with `pgtrigger.register` and supplied with
    `pgtrigger.Trigger` objects. These will automatically be installed after
    migrations. Users can use Django idioms such as ``Q`` and ``F`` objects to
    declare trigger conditions, alleviating the need to write raw SQL for a large
    amount of use cases.

    ``django-pgtrigger`` comes built with some derived triggers for expressing
    common patterns. For example, `pgtrigger.Protect` can protect operations
    on a model, such as deletions or updates (e.g. an append-only model). The
    `pgtrigger.Protect` trigger can even target protecting operations on
    specific updates of fields (e.g. don't allow updates if ``is_active`` is
    ``False`` on a model). Another derived trigger, `pgtrigger.SoftDelete`,
    can soft-delete models by setting a field to ``False`` when a deletion
    happens on the model.


# Changelog
## 2.3.2 (2021-05-29)
### Trivial
  - Fixing tags after organization migration [Wes Kendall, 0ba84d2]

## 2.3.1 (2021-05-29)
### Bug
  - Throw errors on invalid trigger definitions. [Wes Kendall, 28f1329]

    Previously triggers were installed with a broad try/except in order to ignore
    errors when installing duplicate triggers. This caused invalid triggers to
    not be installed with no errors thrown.

    The code was updated to catch the specific exception for duplicate triggers
    and allow other trigger errors to surface. A failing test case was
    added.
  - Fix for wrong argument supplied at _get_database fn call [arpit o.O, 2f7cea1]
### Trivial
  - Updated with the latest django app template [Wes Kendall, 9a71227]
  - Fix incorrect name in example [Simon Willison, 069e05a]

## 2.2.1 (2021-02-23)
### Trivial
  - Optionally change "other" DB name if set at all [Tómas Árni Jónasson, 5b24058]

## 2.2.0 (2021-02-09)
### Feature
  - Multiple database support [Wes Kendall, b09ba73]

    Supports multiple-database functionality in all core functions and management commands.
    By default, all functions and management commands operate over all databases in a
    multi-database setup. This behavior can be overridden with the ``--database`` flag.

    When calling ``manage.py migrate``, only the database being migrated will have
    relevant triggers installed. This fits into how Django supports multi-database
    migrations.

## 2.1.0 (2020-10-20)
### Bug
  - Fixed possibility of duplicate trigger function names [Wes Kendall, b9b1552]

    django-pgtrigger previously enforced that no model could have the
    same trigger name, however, the trigger function being called
    is a globally unique name that needs to be checked.

    django-pgtrigger now adds a hash to the trigger function and
    installed trigger name based on the registered model. This
    prevents a global collision for trigger functions.

    Note that this change will make it appear like no triggers
    are installed. Upgrading to this version will involve dropping
    and re-creating existing triggers.

## 2.0.0 (2020-10-12)
### Api-Break
  - Trigger management commands [Wes Kendall, be26d33]

    Adds the ability to manage triggers by name
    with the ``manage.py pgtrigger`` management command. This
    change includes the following subcommands:

    - ``manage.py pgtrigger ls``: List all triggers, their installation
      status, and whether they are enabled or disabled.
    - ``manage.py pgtrigger install``: Install triggers.
    - ``manage.py pgtrigger uninstall``: Uninstall triggers.
    - ``manage.py pgtrigger enable``: Enable triggers.
    - ``manage.py pgtrigger disable``: Disable triggers.
    - ``manage.py pgtrigger prune``: Prune triggers.

    Because of this change, names are now enforced for every trigger
    and must be unique for every model. Users that wish to
    upgrade to this version must now supply a ``name`` keyword
    argument to their triggers.

    Docs were updated with references to the new management commands.

## 1.3.0 (2020-07-23)
### Feature
  - Extend the ``pgtrigger.SoftDelete`` trigger to support more field types. [Wes Kendall, 4dd8cf8]

    ``pgtrigger.SoftDelete`` takes an optional "value" argument to assign to
    the soft-deleted attribute upon deletion. This allows for more flexibility
    in soft-delete models that might, for example, set a ``CharField`` to
    "inactive".
  - ``pgtrigger.FSM`` enforces a finite state machine on a field. [Wes Kendall, bd3980e]

    The ``pgtrigger.FSM`` trigger allows a user to configure a field and
    a set of valid transitions for the field. An error will be raised
    if any transitions happen that are not part of the valid transitions
    list.

    The docs were updated with an example of how to use ``pgtrigger.FSM``.
### Trivial
  - Added trigger cookbook example for how to track history and model changes. [Wes Kendall, 114a70a]
  - Add "versioning" example to trigger cookbook. [Wes Kendall, 842ad5b]
  - Added trigger cookbook example of freezing a published model [Wes Kendall, 994e9da]

## 1.2.0 (2020-07-23)
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


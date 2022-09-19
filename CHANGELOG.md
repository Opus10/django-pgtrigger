# Changelog
## 4.5.3 (2022-09-19)
### Trivial
  - Fix typo in documentation [Francisco Couzo, def5432]
  - Fix issues when using Django's dummy database. [Wesley Kendall, cc1cb95]
  - Fixed minor documentation typos [Wes Kendall, dc473ff]

## 4.5.2 (2022-09-06)
### Trivial
  - Add Soft-Delete Model Manager example to docs [Jason Oppel, 3a46ae7]

## 4.5.1 (2022-09-01)
### Trivial
  - Remove unused migration code and restructure docs [Wes Kendall, a8793fc]
  - Optimize test suite [Wes Kendall, 863fa93]

## 4.5.0 (2022-08-31)
### Bug
  - Migrations properly serialize dynamic triggers and add better support for reverse migrations [Wes Kendall, 2eb3014]

    Triggers that override ``get_func`` or otherwise generate dynamic SQL are properly reflected
    in migrations when the underlying implementation changes. Along with this, migrations now serialize
    SQL objects instead of trigger classes, making it more robust when reversing migrations or
    updating underlying implementations of existing triggers.

    This change updates the hashes of all triggers and thus re-creates all triggers when running
    ``makemigrations`` or when manually installing them.

## 4.4.0 (2022-08-27)
### Bug
  - Pruning/installations fixed for Postgres versions 12 and under. [Wes Kendall, 22d60e9]

    Paritioned table support introduced a bug in using trigger management
    commands for Postgres 12 and under. This has been fixed.
### Trivial
  - Local development enhancements [Wes Kendall, a4d3c9c]

## 4.3.4 (2022-08-26)
### Trivial
  - Test against Django 4.1 and other CI improvements [Wes Kendall, 813f67e]

## 4.3.3 (2022-08-24)
### Trivial
  - Fix ReadTheDocs builds [Wes Kendall, 3870643]

## 4.3.2 (2022-08-20)
### Trivial
  - Fix release note rendering and code formatting changes [Wes Kendall, c834606]

## 4.3.1 (2022-08-19)
### Trivial
  - Fixed ReadTheDocs builds [Wes Kendall, 2cd0c9e]

## 4.3.0 (2022-08-18)
### Feature
  - Support for partitioned tables [Wes Kendall, 863b8cb]

    Installation commands and all core trigger functionality works with partitioned tables.

    Users will need to run
    ``python manage.py pgtrigger install`` to upgrade existing trigger installations,
    otherwise they will appear as outdated when running ``python manage.py pgtrigger ls``.

    Although outdated triggers will still run successfully for non-partitioned tables, this
    backwards compatibility will be removed in version 5.

## 4.2.1 (2022-08-18)
### Trivial
  - Do schema editor patching in ``App.ready()`` instead of module load [Wes Kendall, cce99ce]

## 4.2.0 (2022-08-18)
### Bug
  - Ensure interoperability with other Postgres backends [Wes Kendall, 1c4f480]

    ``django-pgtrigger`` trigger migrations are interoperable with Postgis and
    other Postgres-flavored database backends.

## 4.1.0 (2022-08-17)
### Bug
  - Allow altering columns from trigger conditions [Wes Kendall, 1178457]

    Previously if one changed the column type of a field used in a trigger condition,
    installation would fail because Postgres doesn't allow this.

    The schema editor was patched to allow for this behavior, dropping and recreating
    triggers when column types are altered.

## 4.0.1 (2022-08-15)
### Trivial
  - Fixed minor issue in settings preventing docs from being built [Wes Kendall, 5ad18f8]

## 4.0.0 (2022-08-15)
### Api-Break
  - Multi-database and registry behavior changed [Wes Kendall, 0663807]

    There were four key additions around multi-datbase and multi-schema
    support:

    1. When using a multi-datbase environment, ``django-pgtrigger``
       now uses ``allow_migrate`` of the router rather than ``db_for_write``
       to determine if a trigger should be installed for a model.

    2. Management commands were changed to operate on one database at a time
       to be consistent with Django management commands. Install, uninstall,
       prune, disable, enable, and ls all take an optional ``--database``
       argument.

    3. ``pgtrigger.ignore``, ``pgtrigger.constraints``, and ``pgtrigger.schema``
       were all updated to take a ``databases`` argument, defaulting to
       working on every postgres database when used for dynamic runtime behavior.

    4. The Postgres function used by ``pgtrigger.ignore`` is always installed
       in the public schema by default. It is referenced using its fully-qualified
       path. The schema can be changed with ``settings.PGTRIGGER_SCHEMA``. Setting
       it to ``None`` will use the schema in the search path. Because of this
       change, the SQL for installed triggers changes, which causes triggers to
       appear as outdated when listing them. This can be fixed by running
       ``manage.py pgtrigger install`` to re-install triggers.

    Along with this, there were a few other breaking changes to the API:

    1. ``pgtrigger.get`` was renamed to ``pgtrigger.registered``.
    2. ``manage.py pgtrigger ls`` shows the trigger status followed by the URI in
       each line of output.

    type: api-break
### Bug
  - Reference ``UpdateSearchVector`` trigger columns correctly [Wes Kendall, 7d40894]

    Columns configured in the ``UpdateSearchVector`` trigger were previously
    referenced in SQL by their model field name and not their column name.
### Feature
  - Added multi-schema support [Wes Kendall, 98342f2]

    ``django-pgtrigger`` didn't handle multiple schemas well, causing some issues for
    legacy installation commands.

    Multiple schema support is a first-class citizen. Depending on the database setup, you
    can now take advantage of the ``--schema`` options for management commands to
    dynamically set the schema.

    Docs were added that overview multi-schema support.
### Trivial
  - Added docs for using triggers in abstract models [Wes Kendall, cd215ac]
  - Refactored project structure [Wes Kendall, 4d53eef]

## 3.4.0 (2022-08-11)
### Bug
  - Fixed issues using ``pgtrigger.ignore`` with multiple databases [Wes Kendall, 557f0e1]

    ``pgtrigger.ignore`` now uses the connection of the database router
    when ignoring triggers.
### Feature
  - Add ``pgtrigger.UpdateSearchVector`` to keep search vectors updated [Wes Kendall, 671e8be]

    When using Django's full-text search, one can keep a
    ``SearchVectorField`` updated with the relevant document fields
    by using ``pgtrigger.UpdateSearchVector``.

    An example was added to the trigger cookbook.
  - Added ``pgtrigger.constraints`` for runtime configuration of deferrable triggers [Wes Kendall, 4b77b7b]

    ``pgtrigger.constraints`` mimics Postgres's ``SET CONSTRAINTS`` statement, allowing one
    to dynamically modify when a deferrable trigger runs.

    Documentation was also added for deferrable triggers with an example in the cookbook.
  - Added deferrable triggers [Wes Kendall, fe4f16e]

    Triggers now have an optional ``timing`` argument. If set, triggers
    will be created as "CONSTRAINT" triggers that can be deferred.

    When ``timing`` is set to ``pgtrigger.Immediate``, the trigger will
    run at the end of a statement. ``pgtrigger.Deferred`` will cause
    the trigger to run at the end of the transaction.

    Note that deferrable triggers must have both
    ``pgtrigger.After`` and ``pgtrigger.Row`` values set for the
    ``when`` and ``level`` attributes.

## 3.3.0 (2022-08-10)
### Bug
  - Fixes ignoring triggers with nested transactions [Wes Kendall, d32113d]

    ``pgtrigger.ignore`` avoids injecting SQL when transactions are in a failed
    state, allowing for one to use nested transactions while ignoring triggers.
  - Fixed issue re-installing triggers with different conditions. [Wes Kendall, 68e29d2]

    Triggers with conditions that change were not successfully
    re-installed with ``pgtrigger.install``. Note that this only affects
    legacy installation and not installation with the new migration system.

## 3.2.0 (2022-08-08)
### Feature
  - Support proxy models on default many-to-many "through" relationships. [Wes Kendall, 4cb0f65]

    Previously one had to use an unmanaged model to declare triggers on default
    many-to-many "through" relationships. Users can now define a proxy model
    on these instead.

    Support for unmanaged models was dropped.

## 3.1.0 (2022-08-08)
### Api-Break
  - Integration with Django's migration system. [Wes Kendall, 6916c14]

    Triggers are fully integrated with Django's migration system, and they are no longer
    installed at the end of migrations by default. Users instead need to run
    ``python manage.py makemigrations`` to make trigger migrations for their applications.

    Triggers for models in third-party apps are declared with proxy models. Triggers
    for default many-to-many "through" models are declared with unmanaged models.

    For instructions on upgrading or preserving legacy behavior, see the frequently
    asked questions of the docs.
### Bug
  - Fixed issues with proxy models and M2M "through" models. [Wes Kendall, 52aa81f]

    Proxy models weren't creating migrations, and M2M "through" models are
    handled by making an unmanaged model that points to the right DB table.
### Feature
  - Remove dependency on ``django-pgconnection``. [Wes Kendall, af0c908]

    Users no longer have to wrap ``settings.DATABASES`` with
    ``django-pgconnection`` in order to use the ``pgtrigger.ignore``
    function.

## 2.5.1 (2022-07-31)
### Trivial
  - Updated with latest Django template, fixing doc builds [Wes Kendall, 4b175a4]

## 2.5.0 (2022-07-30)
### Bug
  - Ignore non-postgres databases in global operations [Wes Kendall, a1aff5d]

    Some operations, such as pruning triggers, would iterate over all databases
    in a project, including non-postgres ones. This fix ignores non-postgres
    databases.
  - Fixes transaction leak when using ``pgtrigger.ignore()`` [Wes Kendall, 1501d7e]

    ``pgtrigger.ignore()`` would continue to ignore triggers until the end of the
    transaction once the context manager exited. This is now fixed.
  - Fixed more issues related to custom table names [Wes Kendall, a0e1f6d]

    Fixes and test cases were added for custom table names that collide
    with reserved words.
  - Wrap table names to avoid SQL command conflicts [Zac Miller, 86ee983]

    Prevents models/tables with names like Order from causing Syntax errors
    and add PyCharm .idea/ folder to .gitignore
### Feature
  - Triggers can be specified in model Meta options [Wes Kendall, 5c1cfec]

    Triggers can now be specified with the ``triggers`` attribute of a model's Meta
    options. This still works alongside the old method of using ``pgtrigger.register``.

## 2.4.1 (2022-02-24)
### Trivial
  - Updated with the latest template, dropped 3.6 supported, added Docker-based development [Wes Kendall, 25e0f0d]

## 2.4.0 (2021-08-15)
### Bug
  - Ensure that generated postgres IDs are lowercase [Wes Kendall, 5c12f66]

    django-pgtrigger now ensures that generated postgres IDs are
    lowercase. Postgres IDs are case insensitive, and it django-pgtrigger
    had issues dealing with names that had a mix of cases.
### Feature
  - Add the "declare" portion of a trigger as a top-level attribute [Wes Kendall, cd18512]

    Previously one had to subclass a trigger and override ``get_declare`` in
    order to change how the "DECLARE" fragment of a trigger was rendered.
    Users can now provide ``declare`` to the instantiation of a trigger.

    The documentation was updated to reflect this change.
### Trivial
  - Fix broken code examples in docs [Wes Kendall, 372719c]

## 2.3.3 (2021-08-15)
### Trivial
  - Adjusted max length of trigger names to 47 characters [Wes Kendall, 528140f]
  - Updated to the latest Django app template [Wes Kendall, d2d5328]
  - Change "Delete" to "Update" in tutorial docs [Rich Rauenzahn, 2839a78]

## 2.3.2 (2021-05-30)
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


"""
The primary functional API for pgtrigger
"""
import collections
import contextlib
import logging

from django.db import connections

from pgtrigger import core
from pgtrigger import registry
from pgtrigger import runtime
from pgtrigger import utils


# The core pgtrigger logger
LOGGER = logging.getLogger('pgtrigger')


def register(*triggers):
    """
    Register the given triggers with wrapped Model class.

    Args:
        *triggers (`pgtrigger.Trigger`): Trigger classes to register.

    Examples:
        Register by decorating a model::

            @pgtrigger.register(
                pgtrigger.Protect(
                    name="append_only",
                    operation=(pgtrigger.Update | pgtrigger.Delete)
                )
            )
            class MyModel(models.Model):
                pass

        Register by calling functionally::

            pgtrigger.register(trigger_object)(MyModel)
    """

    def _model_wrapper(model_class):
        for trigger in triggers:
            trigger.register(model_class)

        return model_class

    return _model_wrapper


def get(*uris, database=None):
    """
    Get registered trigger objects.

    Args:
        *uris (str): URIs of triggers to get. If none are provided,
            all triggers are returned. URIs are in the format of
            ``{app_label}.{model_name}:{trigger_name}``.
        database (Union[str, List[str]], default=None): Only get triggers from this
            database or list of databases.

    Returns:
        List[`pgtrigger.Trigger`]: Matching trigger objects.
    """
    if database and uris:
        raise ValueError('Cannot supply both trigger URIs and a database')

    if not database:
        databases = {utils.database(model) for model, _ in registry.values()}
    else:
        databases = [database] if isinstance(database, str) else database

    if uris:
        for uri in uris:
            if uri and len(uri.split(':')) == 1:
                raise ValueError(
                    'Trigger URI must be in the format of "app_label.model_name:trigger_name"'
                )
            elif uri and not registry.get(uri, None):
                raise ValueError(f'URI "{uri}" not found in pgtrigger registry')

        return [registry.get(uri) for uri in uris]
    else:
        return [
            (model, trigger)
            for model, trigger in registry.values()
            if utils.database(model) in databases
        ]


def install(*uris, database=None):
    """
    Install triggers.

    Args:
        *uris (str): URIs of triggers to install. If none are provided,
            all triggers are installed and orphaned triggers are pruned.
        database (Union[str, List[str]], default=None): Only install triggers from this
            database or list of databases.
    """
    if uris:
        model_triggers = get(*uris, database=database)
    else:
        model_triggers = [
            (model, trigger)
            for model, trigger in get(database=database)
            if trigger.get_installation_status(model)[0] != core.INSTALLED
        ]

    for model, trigger in model_triggers:
        LOGGER.info(
            f'pgtrigger: Installing {trigger} trigger'
            f' for {model._meta.db_table} table'
            f' on {utils.database(model)} database.'
        )
        trigger.install(model)

    if not uris:  # pragma: no branch
        prune(database=database)


def prunable(database=None):
    """Return triggers that are candidates for pruning

    Args:
        database (Union[str, List[str]], default=None): Only return results from this
            database or list of databases. Defaults to returning results from all databases
    """
    installed = {
        (utils.quote(model._meta.db_table), trigger.get_pgid(model)) for model, trigger in get()
    }
    prune_list = []
    for database in utils.postgres_databases(database):
        with connections[database].cursor() as cursor:
            # Only select triggers that are in the current search path. We accomplish
            # this by parsing the tgrelid and only selecting triggers that don't have
            # a schema name in their path
            cursor.execute(
                '''
                SELECT tgrelid::regclass, tgname, tgenabled
                    FROM pg_trigger
                    WHERE tgname LIKE 'pgtrigger_%' AND
                          array_length(parse_ident(tgrelid::regclass::varchar), 1) = 1
                '''
            )
            triggers = set(cursor.fetchall())

        prune_list += [
            (trigger[0], trigger[1], trigger[2] == 'O', database)
            for trigger in triggers
            if (utils.quote(trigger[0]), trigger[1]) not in installed
        ]

    return prune_list


def prune(database=None):
    """
    Remove any pgtrigger triggers in the database that are not used by models.
    I.e. if a model or trigger definition is deleted from a model, ensure
    it is removed from the database

    Args:
        database (Union[str, List[str]], default=None): Only prune triggers from this
            database or list of databases.
    """
    for trigger in prunable(database=database):
        LOGGER.info(
            f'pgtrigger: Pruning trigger {trigger[1]}'
            f' for table {trigger[0]} on {trigger[3]} database.'
        )

        connection = connections[trigger[3]]
        uninstall_sql = utils.render_uninstall(trigger[0], trigger[1])
        with connection.cursor() as cursor:
            cursor.execute(uninstall_sql)


def enable(*uris, database=None):
    """
    Enables registered triggers.

    Args:
        *uris (str): URIs of triggers to enable. If none are provided,
            all triggers are enabled.
        database (Union[str, List[str]], default=None): Only enable triggers from this
            database or list of databases.
    """
    if uris:
        model_triggers = get(*uris, database=database)
    else:
        model_triggers = [
            (model, trigger)
            for model, trigger in get(database=database)
            if trigger.get_installation_status(model)[1] is False
        ]

    for model, trigger in model_triggers:
        LOGGER.info(
            f'pgtrigger: Enabling {trigger} trigger'
            f' for {model._meta.db_table} table'
            f' on {utils.database(model)} database.'
        )
        trigger.enable(model)


def uninstall(*uris, database=None):
    """
    Uninstalls triggers.

    Args:
        *uris (str): URIs of triggers to uninstall. If none are provided,
            all triggers are uninstalled and orphaned triggers are pruned.
        database (Union[str, List[str]], default=None): Only uninstall triggers from this
            database or list of databases.
    """
    if uris:
        model_triggers = get(*uris, database=database)
    else:
        model_triggers = [
            (model, trigger)
            for model, trigger in get(database=database)
            if trigger.get_installation_status(model)[0] != core.UNINSTALLED
        ]

    for model, trigger in model_triggers:
        LOGGER.info(
            f'pgtrigger: Uninstalling {trigger} trigger'
            f' for {model._meta.db_table} table'
            f' on {utils.database(model)} database.'
        )
        trigger.uninstall(model)

    if not uris:
        prune(database=database)


def disable(*uris, database=None):
    """
    Disables triggers.

    Args:
        *uris (str): URIs of triggers to disable. If none are provided,
            all triggers are disabled.
        database (Union[str, List[str]], default=None): Only disable triggers from this
            database or list of databases.
    """
    if uris:
        model_triggers = get(*uris, database=database)
    else:
        model_triggers = [
            (model, trigger)
            for model, trigger in get(database=database)
            if trigger.get_installation_status(model)[1]
        ]

    for model, trigger in model_triggers:
        LOGGER.info(
            f'pgtrigger: Disabling {trigger} trigger for'
            f' {model._meta.db_table} table'
            f' on {utils.database(model)} database.'
        )
        trigger.disable(model)


def constraints(timing, *uris):
    """
    Set deferrable constraint timing for the given triggers, which
    will persist until overridden or until end of transaction.
    Must be in a transaction to run this.

    Args:
        timing (``pgtrigger.Timing``): The timing value that overrides
            the default trigger timing.
        *uris (str): Trigger URIs over which to set constraint timing.
            If none are provided, all trigger constraint timing will
            be set. All triggers must be deferrable.

    Raises:
        RuntimeError: If the database of any triggers is not in a transaction.
        ValueError: If any triggers are not deferrable.
    """

    model_triggers_by_db = collections.defaultdict(list)
    for model, trigger in get(*uris):
        if not trigger.timing:
            raise ValueError(
                f"Trigger {trigger.name} on model {model._meta.label_lower} is not deferrable."
            )

        model_triggers_by_db[utils.database(model)].append((model, trigger))

    for db, model_triggers in model_triggers_by_db.items():
        if not connections[db].in_atomic_block:
            raise RuntimeError(f"Database {db} is not in a transaction.")

        names = ', '.join(trigger.get_pgid(model) for model, trigger in model_triggers)

        with connections[db].cursor() as cursor:
            cursor.execute(f'SET CONSTRAINTS {names} {timing}')


@contextlib.contextmanager
def ignore(*uris):
    """
    Dynamically ignore registered triggers matching URIs from executing in
    an individual thread.
    If no URIs are provided, ignore all pgtriggers from executing in an
    individual thread.

    Args:
        *uris (str): Trigger URIs to ignore. If none are provided, all
            triggers will be ignored.

    Examples:

        Ingore triggers in a context manager::

            with pgtrigger.ignore("my_app.Model:trigger_name"):
                # Do stuff while ignoring trigger

        Ignore multiple triggers as a decorator::

            @pgtrigger.ignore("my_app.Model:trigger_name", "my_app.Model:other_trigger")
            def my_func():
                # Do stuff while ignoring trigger
    """
    with contextlib.ExitStack() as stack:
        for model, trigger in get(*uris):
            stack.enter_context(trigger.ignore(model))

        yield


ignore.session = runtime.ignore_session


@contextlib.contextmanager
def schema(*schemas, database=None):
    """
    Sets the search path to the provided schemas.

    If nested, appends the schemas to the search path if not already in it.

    Args:
        *schemas (str): Schemas that should be appended to the search path.
            Schemas already in the search path from nested calls will not be
            appended.
        database (Union[str, List[str]], default=None): The database or
            list of databases over which the search path should be changed.
            If none, all databases will be affected.
    """
    with contextlib.ExitStack() as stack:
        for database in utils.postgres_databases(database):
            stack.enter_context(runtime.schema(connections[database], *schemas))

        yield


schema.session = runtime.schema_session

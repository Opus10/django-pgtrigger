"""
The primary functional API for pgtrigger
"""
import logging

from django.db import connections, DEFAULT_DB_ALIAS

from pgtrigger import features
from pgtrigger import registry
from pgtrigger import utils


# The core pgtrigger logger
LOGGER = logging.getLogger('pgtrigger')


def install(*uris, database=None):
    """
    Install triggers.

    Args:
        *uris (str): URIs of triggers to install. If none are provided,
            all triggers are installed and orphaned triggers are pruned.
        database (str, default=None): The database. Defaults to
            the "default" database.
    """
    for model, trigger in registry.registered(*uris):
        LOGGER.info(
            f'pgtrigger: Installing {trigger} trigger'
            f' for {model._meta.db_table} table'
            f' on {database or DEFAULT_DB_ALIAS} database.'
        )
        trigger.install(model, database=database)

    if not uris and features.prune_on_install():  # pragma: no branch
        prune(database=database)


def prunable(database=None):
    """Return triggers that are candidates for pruning

    Args:
        database (str, default=None): The database. Defaults to
            the "default" database.
    """
    if not utils.is_postgres(database):
        return []

    registered = {
        (utils.quote(model._meta.db_table), trigger.get_pgid(model))
        for model, trigger in registry.registered()
    }

    with utils.connection(database).cursor() as cursor:
        # Only select triggers that are in the current search path. We accomplish
        # this by parsing the tgrelid and only selecting triggers that don't have
        # a schema name in their path
        cursor.execute(
            '''
            SELECT tgrelid::regclass, tgname, tgenabled
                FROM pg_trigger
                WHERE tgname LIKE 'pgtrigger_%' AND
                      tgparentid = 0 AND
                      array_length(parse_ident(tgrelid::regclass::varchar), 1) = 1
            '''
        )
        triggers = set(cursor.fetchall())

    return [
        (trigger[0], trigger[1], trigger[2] == 'O', database or DEFAULT_DB_ALIAS)
        for trigger in triggers
        if (utils.quote(trigger[0]), trigger[1]) not in registered
    ]


def prune(database=None):
    """
    Remove any pgtrigger triggers in the database that are not used by models.
    I.e. if a model or trigger definition is deleted from a model, ensure
    it is removed from the database

    Args:
        database (str, default=None): The database. Defaults to
            the "default" database.
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
        database (str, default=None): The database. Defaults to
            the "default" database.
    """
    for model, trigger in registry.registered(*uris):
        LOGGER.info(
            f'pgtrigger: Enabling {trigger} trigger'
            f' for {model._meta.db_table} table'
            f' on {database or DEFAULT_DB_ALIAS} database.'
        )
        trigger.enable(model, database=database)


def uninstall(*uris, database=None):
    """
    Uninstalls triggers.

    Args:
        *uris (str): URIs of triggers to uninstall. If none are provided,
            all triggers are uninstalled and orphaned triggers are pruned.
        database (str, default=None): The database. Defaults to
            the "default" database.
    """
    for model, trigger in registry.registered(*uris):
        LOGGER.info(
            f'pgtrigger: Uninstalling {trigger} trigger'
            f' for {model._meta.db_table} table'
            f' on {database or DEFAULT_DB_ALIAS} database.'
        )
        trigger.uninstall(model, database=database)

    if not uris and features.prune_on_install():
        prune(database=database)


def disable(*uris, database=None):
    """
    Disables triggers.

    Args:
        *uris (str): URIs of triggers to disable. If none are provided,
            all triggers are disabled.
        database (str, default=None): The database. Defaults to
            the "default" database.
    """
    for model, trigger in registry.registered(*uris):
        LOGGER.info(
            f'pgtrigger: Disabling {trigger} trigger for'
            f' {model._meta.db_table} table'
            f' on {database or DEFAULT_DB_ALIAS} database.'
        )
        trigger.disable(model, database=database)

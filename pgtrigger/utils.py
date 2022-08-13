from django.conf import settings
from django.db import connections, DEFAULT_DB_ALIAS, router


def postgres_databases(database=None):
    """Return postgres databases from the provided database or list of databases.

    If no database is provided, return all postgres databases
    """
    databases = [database] if isinstance(database, str) else database or settings.DATABASES
    return [database for database in databases if connections[database].vendor == 'postgresql']


def quote(label):
    """Conditionally wraps a label in quotes"""
    if label.startswith('"') or label.endswith('"'):
        return label
    else:
        return f'"{label}"'


def database(model):
    """
    Obtains the database used for a trigger / model pair. The database
    for the connection is selected based on the write DB in the database
    router config.
    """
    return router.db_for_write(model) or DEFAULT_DB_ALIAS


def connection(model):
    """
    Obtains the connection used for a trigger / model pair. The database
    for the connection is selected based on the write DB in the database
    router config.
    """
    return connections[database(model)]


def render_uninstall(table, trigger_pgid):
    """Renders uninstallation SQL"""
    return f'DROP TRIGGER IF EXISTS {trigger_pgid} ON {quote(table)};'

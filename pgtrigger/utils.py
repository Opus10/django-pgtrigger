from django.conf import settings
from django.db import connections, DEFAULT_DB_ALIAS


def connection(database=None):
    """
    Obtains the connection used for a trigger / model pair. The database
    for the connection is selected based on the write DB in the database
    router config.
    """
    return connections[database or DEFAULT_DB_ALIAS]


def is_postgres(database):
    return connection(database).vendor == 'postgresql'


def postgres_databases(databases=None):
    """Return postgres databases from the provided list of databases.

    If no databases are provided, return all postgres databases
    """
    databases = databases or list(settings.DATABASES)
    assert isinstance(databases, list)
    return [database for database in databases if is_postgres(database)]


def exec_sql(sql, database=None, fetchall=False):
    if is_postgres(database):  # pragma: no branch
        with connection(database).cursor() as cursor:
            cursor.execute(sql)

            if fetchall:
                return cursor.fetchall()


def quote(label):
    """Conditionally wraps a label in quotes"""
    if label.startswith('"') or label.endswith('"'):
        return label
    else:
        return f'"{label}"'


def render_uninstall(table, trigger_pgid):
    """Renders uninstallation SQL"""
    return f'DROP TRIGGER IF EXISTS {trigger_pgid} ON {quote(table)};'

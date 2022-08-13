from django.conf import settings
from django.db import connections


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

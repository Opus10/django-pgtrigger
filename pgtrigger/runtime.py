"""
Functions for runtime-configuration of triggers, such as ignoring
them or dynamically setting the search path.
"""
import contextlib
import threading

from django.db import connections
import psycopg2.extensions

import pgtrigger.utils


# All triggers currently being ignored
_ignore = threading.local()

# All schemas in the search path
_schema = threading.local()


def _is_concurrent_statement(sql):
    """
    True if the sql statement is concurrent and cannot be ran in a transaction
    """
    sql = sql.strip().lower() if sql else ''
    return sql.startswith('create') and 'concurrently' in sql


def _is_transaction_errored(cursor):
    """
    True if the current transaction is in an errored state
    """
    return (
        cursor.connection.get_transaction_status()
        == psycopg2.extensions.TRANSACTION_STATUS_INERROR
    )


def _can_inject_variable(cursor, sql):
    """True if we can inject a SQL variable into a statement.

    A named cursor automatically prepends
    "NO SCROLL CURSOR WITHOUT HOLD FOR" to the query, which
    causes invalid SQL to be generated. There is no way
    to override this behavior in psycopg2, so ignoring triggers
    cannot happen for named cursors. Django only names cursors
    for iterators and other statements that read the database,
    so it seems to be safe to ignore named cursors.

    Concurrent index creation is also incompatible with local variable
    setting. Ignore these cases for now.
    """
    return (
        not cursor.name
        and not _is_concurrent_statement(sql)
        and not _is_transaction_errored(cursor)
    )


def _inject_pgtrigger_ignore(execute, sql, params, many, context):
    """
    A connection execution wrapper that sets a pgtrigger.ignore
    variable in the executed SQL. This lets other triggers know when
    they should ignore execution
    """
    if _can_inject_variable(context['cursor'], sql):
        sql = "SET LOCAL pgtrigger.ignore='{" + ",".join(_ignore.value) + "}';" + sql

    return execute(sql, params, many, context)


def _inject_schema(execute, sql, params, many, context):
    """
    A connection execution wrapper that sets the schema
    variable in the executed SQL.
    """
    if _can_inject_variable(context['cursor'], sql) and _schema.value:
        sql = (
            "SET LOCAL search_path="
            + ",".join(pgtrigger.utils.quote(val) for val in _schema.value)
            + ";"
            + sql
        )

    return execute(sql, params, many, context)


@contextlib.contextmanager
def _ignore_session(connection):
    """Main implementation of starting an ignore session for a single connection"""
    if _inject_pgtrigger_ignore not in connection.execute_wrappers:
        with connection.execute_wrapper(_inject_pgtrigger_ignore):
            yield

            if connection.in_atomic_block:
                # We've finished ignoring triggers and are in a transaction,
                # so flush the local variable.
                with connection.cursor() as cursor:
                    cursor.execute('RESET pgtrigger.ignore;')
    else:
        yield


@contextlib.contextmanager
def ignore_session(database=None):
    """Starts a session where triggers can be ignored

    The session is started for the provided database or list of
    databases. If no databases are provided, it's started for
    every database.
    """
    if not hasattr(_ignore, 'value'):
        _ignore.value = set()

    with contextlib.ExitStack() as contexts:
        for database in pgtrigger.utils.postgres_databases(database):
            contexts.enter_context(_ignore_session(connections[database]))

        yield


@contextlib.contextmanager
def ignore(connection, ignore_uri):
    """
    Ignores a single trigger
    """
    with ignore_session(connection.alias):
        if ignore_uri not in _ignore.value:
            try:
                _ignore.value.add(ignore_uri)
                yield
            finally:
                _ignore.value.remove(ignore_uri)
        else:  # The trigger is already being ignored
            yield


@contextlib.contextmanager
def _schema_session(connection):
    """Implementation to start a search path session for a single connection"""

    if _inject_schema not in connection.execute_wrappers:
        if connection.in_atomic_block:
            # If this is the first time we are setting the search path,
            # register the pre_execute_hook and store a reference to the original
            # search path. Note that we must use this approach because we cannot
            # simply RESET the search_path at the end. A user may have previously
            # set it
            with connection.cursor() as cursor:
                cursor.execute("SHOW search_path;")
                initial_search_path = cursor.fetchall()[0][0]

        with connection.execute_wrapper(_inject_schema):
            yield

            if connection.in_atomic_block:
                # We've finished modifying the search path and are in a transaction,
                # so flush the local variable
                with connection.cursor() as cursor:
                    cursor.execute(f'SET search_path={initial_search_path};')
    else:
        yield


@contextlib.contextmanager
def schema_session(database=None):
    """Starts a session where the search path can be modified

    The session is started for the provided database or list of
    databases. If no databases are provided, it's started for
    every database.
    """
    if not hasattr(_schema, 'value'):
        # Use a list instead of a set because ordering is important to the search path
        _schema.value = []

    with contextlib.ExitStack() as contexts:
        for database in pgtrigger.utils.postgres_databases(database):
            contexts.enter_context(_schema_session(connections[database]))

        yield


@contextlib.contextmanager
def schema(connection, *schemas):
    database = connection.alias

    with schema_session(database):
        schemas = [s for s in schemas if s not in _schema.value]
        try:
            _schema.value.extend(schemas)
            yield
        finally:
            for s in schemas:
                _schema.value.remove(s)

import contextlib

import django
from django.db import connections, DEFAULT_DB_ALIAS, transaction as db_transaction
from django.db.utils import InternalError, ProgrammingError
import pytest


@contextlib.contextmanager
def raises_trigger_error(match=None, database=DEFAULT_DB_ALIAS, transaction=None):
    with contextlib.ExitStack() as stack:
        # psycopg 3 changes the exception type
        if django.VERSION >= (4, 2):
            exc_class = ProgrammingError
        else:
            exc_class = InternalError

        stack.enter_context(pytest.raises(exc_class, match=match))

        if transaction is None:
            transaction = connections[database].in_atomic_block

        if transaction:
            stack.enter_context(db_transaction.atomic(using=database))

        yield

import contextlib

import pytest
from django.db import DEFAULT_DB_ALIAS, connections
from django.db import transaction as db_transaction
from django.db.utils import DatabaseError


@contextlib.contextmanager
def raises_trigger_error(match=None, database=DEFAULT_DB_ALIAS, transaction=None):
    with contextlib.ExitStack() as stack:
        stack.enter_context(pytest.raises(DatabaseError, match=match))

        if transaction is None:
            transaction = connections[database].in_atomic_block

        if transaction:
            stack.enter_context(db_transaction.atomic(using=database))

        yield

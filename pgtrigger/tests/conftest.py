from django.core.management import call_command
from django.db import connection
import pytest


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker, request):
    with django_db_blocker.unblock():
        # Create schemas required for testing
        with connection.cursor() as cursor:
            try:
                cursor.execute('CREATE SCHEMA "order";')
            except Exception:
                pass

            try:
                cursor.execute('CREATE SCHEMA receipt;')
            except Exception:
                pass

        call_command('migrate', database='order', verbosity=request.config.option.verbose)
        call_command('migrate', database='receipt', verbosity=request.config.option.verbose)


@pytest.fixture(autouse=True)
def disable_logging(mocker):
    mocker.patch("pgtrigger.management.commands.pgtrigger._setup_logging", autospec=True)

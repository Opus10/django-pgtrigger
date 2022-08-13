from django.db import connection
import pytest

import pgtrigger.core


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
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

        # Some tests at the end leak into the next test run when re-using the DB.
        # Ensure triggers are installed when the test suite starts
        pgtrigger.core.install()


@pytest.fixture(autouse=True)
def disable_logging(mocker):
    mocker.patch("pgtrigger.management.commands.pgtrigger._setup_logging", autospec=True)


@pytest.fixture
def ignore_schema_databases(settings):
    """Configure settings to ignore databases that use schemas"""
    settings.DATABASES = {
        key: val for key, val in settings.DATABASES.items() if key not in ("order", "receipt")
    }

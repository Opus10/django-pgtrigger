from django.core.management import call_command
import pytest


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker, request):
    with django_db_blocker.unblock():
        # Note - schemas for databases are made in the pre-migrate hook
        # The django test runner only runs migrations ones per unique connection string.
        # Ensure that we've migrated all of our schema-based databases here
        call_command('migrate', database='default', verbosity=request.config.option.verbose)
        call_command('migrate', database='order', verbosity=request.config.option.verbose)
        call_command('migrate', database='receipt', verbosity=request.config.option.verbose)


@pytest.fixture(autouse=True)
def disable_logging(mocker):
    mocker.patch("pgtrigger.management.commands.pgtrigger._setup_logging", autospec=True)

import pytest

import pgtrigger


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        # Some tests at the end leak into the next test run when re-using the DB.
        # Ensure triggers are installed when the test suite starts
        pgtrigger.install()

"""Tests behavior related to migrations"""
import pathlib
import shutil

import ddf
import django.contrib.auth.models as auth_models
from django.core import checks
from django.core.management import call_command
from django.db.utils import InternalError
import pytest

import pgtrigger
from pgtrigger.tests import models


@pytest.fixture
def clean_migrations():
    pass


def test_checks():
    assert not checks.run_checks()


@pytest.fixture
def reset_migrations(tmp_path):
    """Ensures the migration dir is reset after the test"""
    migration_dir = pathlib.Path(__file__).parent / "migrations"
    num_migrations = len(list(migration_dir.glob("0*.py")))
    shutil.copytree(migration_dir, tmp_path / "migrations")

    yield

    # Migrate back to the initial migration of the test to allevitate
    # some of the issues when re-using a test DB
    call_command("migrate", "tests", str(num_migrations).rjust(4, "0"))

    shutil.rmtree(migration_dir)
    shutil.copytree(tmp_path / "migrations", migration_dir)


def _num_files(dir_path):
    return len(list(dir_path.iterdir()))


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("reset_migrations")
@pytest.mark.order(
    -1
)  # This is a possibly leaky test that modifies the schema. Always run second to last
def test_makemigrations(settings):
    """
    pgtrigger migrations are turned on in test mode. Create
    the new migration file here, apply migrations, and test
    other operations that alter migrations
    """
    assert not settings.PGTRIGGER_INSTALL_ON_MIGRATE
    assert settings.PGTRIGGER_MIGRATIONS

    migration_dir = pathlib.Path(__file__).parent / "migrations"
    num_orig_migrations = _num_files(migration_dir)

    call_command("makemigrations")
    assert _num_files(migration_dir) == num_orig_migrations + 1

    call_command("migrate")

    # Add a new trigger to the registry that should be migrated
    trigger = pgtrigger.Trigger(
        when=pgtrigger.Before,
        name='my_migrated_trigger',
        operation=pgtrigger.Insert | pgtrigger.Update,
        func="RAISE EXCEPTION 'no no no!';",
    )

    with trigger.register(models.TestModel):
        call_command("makemigrations")
        assert _num_files(migration_dir) == num_orig_migrations + 2

        # As a sanity check, ensure makemigrations doesnt make dups
        call_command("makemigrations")
        assert _num_files(migration_dir) == num_orig_migrations + 2

        # Before migrating, I should be able to make a ``TestModel``
        ddf.G("tests.TestModel")

        call_command("migrate")

        # After migrating, test models should be protected
        with pytest.raises(InternalError, match='no no no!'):
            models.TestModel.objects.create()

        # Update the trigger to allow inserts, but not updates.
        # We should have a new migration
        trigger.operation = pgtrigger.Update
        call_command("makemigrations")
        assert _num_files(migration_dir) == num_orig_migrations + 3

        call_command("migrate")

        # We should be able to make test models but not update them
        test_model = ddf.G("tests.TestModel")
        with pytest.raises(InternalError, match='no no no!'):
            test_model.save()

    # The trigger is now removed from the registry. It should create
    # a new migration
    call_command("makemigrations")
    assert _num_files(migration_dir) == num_orig_migrations + 4

    call_command("migrate")
    # We should be able to create and update the test model now that
    # the trigger is removed
    test_model = ddf.G("tests.TestModel")
    test_model.save()

    # Create a protection trigger on the external user model and
    # migrate it
    trigger = pgtrigger.Trigger(
        when=pgtrigger.Before,
        name='nothing_allowed',
        operation=pgtrigger.Insert | pgtrigger.Update,
        func="RAISE EXCEPTION 'no no no!';",
    )

    with trigger.register(auth_models.User):
        call_command("pgtrigger", "makemigrations", "auth", "tests")
        assert _num_files(migration_dir) == num_orig_migrations + 5

        call_command("migrate")

        # After migrating, user models should be protected
        with pytest.raises(InternalError, match='no no no!'):
            auth_models.User.objects.create(username="hi")

        # No new migrations should be created
        call_command("pgtrigger", "makemigrations", "auth", "tests")
        assert _num_files(migration_dir) == num_orig_migrations + 5

    # After de-registering, we should get a new migration
    call_command("pgtrigger", "makemigrations", "auth", "tests")
    assert _num_files(migration_dir) == num_orig_migrations + 6

    call_command("migrate")
    # We should be able to make users
    ddf.G(auth_models.User)

    # Test that special characters are escaped
    trigger = pgtrigger.Protect(
        name='special_characters',
        operation=pgtrigger.Update,
        condition=pgtrigger.Q(new__char_field="%"),
    )
    with trigger.register(models.TestModel):
        call_command("makemigrations")
        assert _num_files(migration_dir) == num_orig_migrations + 7

        call_command("migrate")

        tm = ddf.G("tests.TestModel", char_field="hello")

        with pytest.raises(InternalError, match='Cannot update rows'):
            tm.char_field = "%"
            tm.save()

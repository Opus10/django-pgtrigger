import ddf
import pytest
from django.db import IntegrityError, connection, transaction

import pgtrigger
import pgtrigger.utils
from pgtrigger.tests import models, utils

if pgtrigger.utils.psycopg_maj_version == 3:
    from psycopg.sql import SQL, Identifier
elif pgtrigger.utils.psycopg_maj_version == 2:
    from psycopg2.sql import SQL, Identifier
else:
    raise AssertionError


@pytest.mark.django_db
def test_schema():
    """Verifies behavior of pgtrigger.schema"""

    def _search_path():
        with connection.cursor() as cursor:
            cursor.execute("SHOW search_path;")
            return cursor.fetchall()[0][0]

    assert _search_path() == '"$user", public'

    with pgtrigger.schema("hello"):
        assert _search_path() == "hello"

        with pgtrigger.schema("hello", "$user"):
            assert _search_path() == 'hello, "$user"'

        assert _search_path() == "hello"

    with connection.cursor() as cursor:
        cursor.execute("SET search_path=custom;")

    with transaction.atomic():
        assert _search_path() == "custom"

        with pgtrigger.schema("hello", databases=["default"]):
            assert _search_path() == "hello"

        assert _search_path() == "custom"

    with pgtrigger.schema.session(databases=["default"]):
        assert _search_path() == "custom"

    assert _search_path() == "custom"


@pytest.mark.django_db(transaction=True)
def test_constraints():
    """
    Tests running [pgtrigger.constraints][] on deferrable triggers
    """
    # Not every trigger is deferrable, so this should raise an error
    with transaction.atomic():
        with pytest.raises(ValueError, match="is not deferrable"):
            pgtrigger.constraints(pgtrigger.Immediate)

    # Make the LogEntry model a soft delete model where
    # "level" is set to "inactive"
    trigger = pgtrigger.Protect(
        name="protect_delete",
        when=pgtrigger.After,
        operation=pgtrigger.Delete,
        timing=pgtrigger.Deferred,
    )
    with trigger.register(models.TestModel), trigger.install(models.TestModel):
        # Verify we have to be in a transaction
        with pytest.raises(RuntimeError, match="not in a transaction"):
            pgtrigger.constraints(pgtrigger.Immediate, "tests.TestModel:protect_delete")

        obj = ddf.G(models.TestModel)
        with transaction.atomic():
            # This "with" is only here to validate that ignoring the trigger will
            # NOT happen. After this "with" is done, the transaction still hasn't finished
            # and the trigger hasn't executed yet, so it won't be ignored.
            with pgtrigger.ignore("tests.TestModel:protect_delete"):
                obj.delete()
                # Deletion works within the transaction so far since trigger is deferred
                assert not models.TestModel.objects.exists()

            # When we set constraints to Immediate, it should fail inside
            # of the transaction
            with utils.raises_trigger_error(match="Cannot delete", transaction=False):
                # The first statement does nothing because the trigger is already deferred
                pgtrigger.constraints(
                    pgtrigger.Deferred, "tests.TestModel:protect_delete", databases=["default"]
                )
                pgtrigger.constraints(
                    pgtrigger.Immediate, "tests.TestModel:protect_delete", databases=["default"]
                )


@pytest.mark.django_db(transaction=True)
def test_ignore_nested_transactions():
    """Verifies a trigger can be ignored during nested transactions"""
    ddf.G(models.CustomTableName, int_field=1)
    trigger = pgtrigger.Protect(
        name="protect_insert",
        when=pgtrigger.Before,
        operation=pgtrigger.Insert,
    )
    with trigger.register(models.CustomTableName):
        with trigger.install(models.CustomTableName):
            with transaction.atomic():
                with pgtrigger.ignore("tests.CustomTableName:protect_insert"):
                    try:
                        with transaction.atomic():  # pragma: no branch
                            models.CustomTableName.objects.create(int_field=1)
                    except IntegrityError:
                        models.CustomTableName.objects.create(int_field=2)


@pytest.mark.django_db(transaction=True)
def test_ignore_session():
    """Verifies an ignore session can be used to avoid transaction-related issues"""
    ddf.G(models.CustomTableName, int_field=1)
    trigger = pgtrigger.Protect(
        name="protect_insert",
        when=pgtrigger.Before,
        operation=pgtrigger.Insert,
    )
    with trigger.register(models.CustomTableName), trigger.install(models.CustomTableName):
        with pgtrigger.ignore.session():
            with transaction.atomic():
                with pgtrigger.ignore("tests.CustomTableName:protect_insert"):
                    try:
                        models.CustomTableName.objects.create(int_field=1)
                    except IntegrityError:
                        pass


@pytest.mark.django_db
def test_ignore_no_transaction_leaks():
    """Verify ignore does not leak during a transaction"""
    deletion_protected_model = ddf.G(models.TestTrigger)
    with pgtrigger.ignore("tests.TestTriggerProxy:protect_delete"):
        deletion_protected_model.delete()
        assert not models.TestTrigger.objects.exists()

    deletion_protected_model = ddf.G(models.TestTrigger)
    with utils.raises_trigger_error(match="Cannot delete rows"):
        deletion_protected_model.delete()


@pytest.mark.django_db
@pytest.mark.parametrize("model_class", [models.TestTriggerProxy, models.CustomTableName])
def test_basic_ignore(model_class):
    """Verify basic dynamic ignore functionality"""
    deletion_protected_model = ddf.G(model_class)
    with utils.raises_trigger_error(match="Cannot delete rows"):
        deletion_protected_model.delete()

    with pgtrigger.ignore(f"tests.{model_class.__name__}:protect_delete"):
        deletion_protected_model.delete()

    assert not models.TestTrigger.objects.exists()

    deletion_protected_model = ddf.G(model_class)
    with utils.raises_trigger_error(match="Cannot delete rows"):
        deletion_protected_model.delete()

    # Verify that named cursors are ignored and that valid SQL is still generated
    with pgtrigger.ignore(f"tests.{model_class.__name__}:protect_delete"):
        assert len(list(model_class.objects.all().iterator())) == 1


@pytest.mark.django_db
def test_nested_ignore():
    """Test nesting pgtrigger.ignore()"""
    deletion_protected_model1 = ddf.G(models.TestTrigger)
    deletion_protected_model2 = ddf.G(models.TestTrigger)
    with utils.raises_trigger_error(match="Cannot delete rows"):
        deletion_protected_model1.delete()

    with pgtrigger.ignore("tests.TestTriggerProxy:protect_delete"):
        with pgtrigger.ignore("tests.TestTriggerProxy:protect_delete"):
            deletion_protected_model1.delete()
        deletion_protected_model2.delete()

    assert not models.TestTrigger.objects.exists()

    deletion_protected_model = ddf.G(models.TestTrigger)
    with utils.raises_trigger_error(match="Cannot delete rows"):
        deletion_protected_model.delete()

    with pgtrigger.ignore.session(databases=["default"]):
        deletion_protected_model = ddf.G(models.TestTrigger)
        with utils.raises_trigger_error(match="Cannot delete rows"):
            deletion_protected_model.delete()


@pytest.mark.django_db
def test_multiple_ignores():
    """Tests multiple pgtrigger.ignore()"""
    deletion_protected_model1 = ddf.G(models.TestTrigger)
    ddf.G(models.TestTrigger)
    with utils.raises_trigger_error(match="Cannot delete rows"):
        deletion_protected_model1.delete()

    ddf.G(models.TestTrigger, field="hi!")
    with utils.raises_trigger_error(match="no no no!"):
        models.TestTrigger.objects.create(field="misc_insert")

    with pgtrigger.ignore("tests.TestTriggerProxy:protect_delete"):
        deletion_protected_model1.delete()
        with utils.raises_trigger_error(match="no no no!"):
            models.TestTrigger.objects.create(field="misc_insert")

        with pgtrigger.ignore("tests.TestTrigger:protect_misc_insert"):
            m = models.TestTrigger.objects.create(field="misc_insert")
            m.delete()

        models.TestTrigger.objects.all().delete()

    assert not models.TestTrigger.objects.exists()

    deletion_protected_model = ddf.G(models.TestTrigger)
    with utils.raises_trigger_error(match="Cannot delete rows"):
        deletion_protected_model.delete()


@pytest.mark.django_db
def test_custom_db_table_ignore():
    """Verify we can ignore triggers on custom table names"""
    deletion_protected_model = ddf.G(models.CustomTableName)

    # Ensure we can ignore the deletion trigger
    with pgtrigger.ignore("tests.CustomTableName:protect_delete"):
        deletion_protected_model.delete()
        assert not models.CustomTableName.objects.exists()


@pytest.mark.skipif(
    pgtrigger.utils.psycopg_maj_version == 3, reason="Psycopg2 preserves entire query"
)
@pytest.mark.django_db
@pytest.mark.parametrize(
    "sql, params",
    [
        ("select count(*) from auth_user where id = %s", (1,)),
        ("select count(*) from auth_user", ()),
        (b"select count(*) from auth_user where id = %s", (1,)),
        (b"select count(*) from auth_user", ()),
    ],
)
def test_inject_trigger_ignore(settings, mocker, sql, params):
    settings.DEBUG = True
    expected_sql_base = "SELECT set_config('pgtrigger.ignore', '{ignored_triggers}', true)"
    # Order isn't deterministic, so we need to check for either order.
    expected_sql_1 = expected_sql_base.format(
        ignored_triggers=r"{tests_testtrigger:pgtrigger_protect_delete_b7483,pgtrigger_protect_delete_b7483}"
    )
    expected_sql_2 = expected_sql_base.format(
        ignored_triggers=r"{pgtrigger_protect_delete_b7483,tests_testtrigger:pgtrigger_protect_delete_b7483}"
    )
    with pgtrigger.ignore("tests.TestTriggerProxy:protect_delete"):
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            query = connection.queries[-1]
            assert query["sql"].startswith(expected_sql_1) or query["sql"].startswith(
                expected_sql_2
            )


@pytest.mark.django_db
def test_test_trigger_ignore_psycopg_sql_objects():
    """Verify that native psycopg SQL objects are handled correctly when ignoring triggers."""
    # Test with a `sql.SQL` object
    with pgtrigger.ignore("tests.TestTrigger:protect_misc_insert"), connection.cursor() as cursor:
        cursor.execute(
            SQL(
                "INSERT INTO tests_testtrigger (field, int_field, dt_field)"
                "VALUES ('misc_insert', 1, now())",
            )
        )
    # Test with a `sql.Composed` object (built through formatting)
    with pgtrigger.ignore("tests.TestTrigger:protect_misc_insert"), connection.cursor() as cursor:
        cursor.execute(
            SQL(
                "INSERT INTO {table} (field, int_field, dt_field) VALUES ('misc_insert', 1, now())"
            ).format(table=Identifier("tests_testtrigger"))
        )

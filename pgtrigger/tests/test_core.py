import datetime as dt

import ddf
from django.contrib.auth.models import User
from django.db import transaction
from django.db.utils import InternalError
from django.db.utils import NotSupportedError
import pytest

import pgtrigger
from pgtrigger import core
from pgtrigger.tests import models


@pytest.mark.django_db(transaction=True)
def test_partition():
    p1 = ddf.G(models.PartitionModel, timestamp=dt.datetime(2019, 1, 3))
    p2 = ddf.G(models.PartitionModel, timestamp=dt.datetime(2019, 2, 4))
    p3 = ddf.G(models.PartitionModel, timestamp=dt.datetime(2019, 3, 5))
    default = ddf.G(models.PartitionModel, timestamp=dt.datetime(2019, 4, 5))

    with pytest.raises(InternalError, match="Cannot delete"):
        p1.delete()

    with pytest.raises(InternalError, match="Cannot delete"):
        p2.delete()

    with pytest.raises(InternalError, match="Cannot delete"):
        p3.delete()

    with pytest.raises(InternalError, match="Cannot delete"):
        default.delete()

    with pgtrigger.ignore("tests.PartitionModel:protect_delete"):
        p1.delete()
        p2.delete()
        p3.delete()
        default.delete()


@pytest.mark.django_db
def test_through_model():
    """
    Tests the "ThroughTrigger" model to verify that triggers execute on M2M through models
    """
    test_trigger = ddf.G(models.TestTrigger)
    test_trigger.m2m_field.add(ddf.G("auth.User"))

    with pytest.raises(InternalError, match="Cannot delete"):
        test_trigger.m2m_field.clear()


@pytest.mark.django_db
def test_statement_row_level_logging():
    """
    Updates "ToLogModel" entries, which have statement, row-level,
    and referencing statement triggers that create log entries.
    """
    ddf.G(models.ToLogModel, n=5, field='old_field')

    assert not models.LogEntry.objects.exists()

    models.ToLogModel.objects.update(field='new_field')

    # The statement-level trigger without references should have produced
    # one log entry
    assert models.LogEntry.objects.filter(level='STATEMENT', old_field__isnull=True).count() == 1

    # The statement-level trigger with references should have made log
    # entries for all of the old values and the new updated values
    assert models.LogEntry.objects.filter(level='STATEMENT', old_field__isnull=False).count() == 5
    assert (
        models.LogEntry.objects.filter(
            level='STATEMENT', old_field='old_field', new_field='new_field'
        ).count()
        == 5
    )

    # The row-level trigger should have produced five entries
    assert models.LogEntry.objects.filter(level='ROW').count() == 5
    obj = models.ToLogModel.objects.first()
    obj.save()

    # A duplicate update shouldn't fire any more row-level log entries
    assert models.LogEntry.objects.filter(level='ROW').count() == 5


@pytest.mark.django_db(transaction=True)
def test_deferred_trigger():
    """
    Tests deferrable execution of a trigger
    """
    # Make the LogEntry model a soft delete model where
    # "level" is set to "inactive"
    trigger = pgtrigger.Protect(
        name='protect_delete',
        when=pgtrigger.After,
        operation=pgtrigger.Delete,
        timing=pgtrigger.Deferred,
    )
    with trigger.register(models.TestModel), trigger.install(models.TestModel):
        obj = ddf.G(models.TestModel)
        deferring_worked = False
        with pytest.raises(InternalError, match="Cannot delete"):
            with transaction.atomic():
                obj.delete()
                # Deletion works within the transaction, but fails
                # when the transaction commits.
                assert not models.TestModel.objects.exists()
                deferring_worked = True

        assert deferring_worked
        assert models.TestModel.objects.exists()
        obj = models.TestModel.objects.get()

        # Verify that we can ignore deferrable triggers
        with pgtrigger.ignore("tests.TestModel:protect_delete"):
            with transaction.atomic():
                obj.delete()
                assert not models.TestModel.objects.exists()

            # The object should still not exist outside of the transaction
            assert not models.TestModel.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_updating_trigger_condition():
    """
    Tests re-installing a trigger when the condition changes
    """
    # Make the LogEntry model a soft delete model where
    # "level" is set to "inactive"
    trigger = pgtrigger.Protect(name='protect_delete', operation=pgtrigger.Delete)
    with trigger.install(models.LogEntry):
        le = ddf.G(models.LogEntry, level="good")

        with pytest.raises(InternalError, match='Cannot delete'):
            le.delete()

        # Protect deletes when "level" is "bad". The trigger should be reinstalled
        # appropriately
        trigger.condition = pgtrigger.Q(old__level="bad")
        with trigger.install(models.LogEntry):
            le.delete()


def test_declaration_rendering():
    """Verifies that triggers with a DECLARE are rendered correctly"""

    class DeclaredTrigger(pgtrigger.Trigger):
        def get_declare(self, model):
            return [('var_name', 'UUID')]

    rendered = DeclaredTrigger(
        name='test', when=pgtrigger.Before, operation=pgtrigger.Insert
    ).render_declare(None)
    assert rendered == 'DECLARE \nvar_name UUID;'


def test_f():
    """Tests various properties of the pgtrigger.F object"""
    with pytest.raises(ValueError, match='must reference'):
        pgtrigger.F('bad_value')

    assert pgtrigger.F('old__value').resolved_name == 'OLD."value"'


@pytest.mark.django_db(transaction=True)
def test_is_distinct_from_condition():
    """Tests triggers where the old and new are distinct from one another

    Note that distinct is the not the same as not being equal since nulls
    are never equal
    """
    test_model = ddf.G(models.TestTrigger, int_field=0)

    # Protect a field from being updated to a different value
    trigger = pgtrigger.Protect(
        name='protect',
        when=pgtrigger.Before,
        operation=pgtrigger.Update,
        condition=pgtrigger.Q(old__int_field__df=pgtrigger.F('new__int_field'))
        | pgtrigger.Q(new__nullable__df=pgtrigger.F('old__nullable')),
    )
    with trigger.install(models.TestTrigger):
        with pytest.raises(InternalError, match='Cannot update rows'):
            test_model.int_field = 1
            test_model.save()

        # Ensure the null case works
        with pytest.raises(InternalError, match='Cannot update rows'):
            test_model.nullable = '1'
            test_model.save()

        # Saving the same values should work fine
        test_model.int_field = 0
        test_model.nullable = None
        test_model.save()


@pytest.mark.django_db(transaction=True)
def test_invalid_trigger():
    """Ensures triggers with invalid syntax are not installed"""
    # Truncates can only be used on statement level triggers
    trigger = pgtrigger.Protect(
        name='test_invalid',
        operation=pgtrigger.Truncate,
    )
    with pytest.raises(NotSupportedError, match='are not supported'):
        trigger.install(models.TestTrigger)


@pytest.mark.django_db(transaction=True)
def test_is_distinct_from_condition_fk_field():
    """Tests triggers where the old and new are distinct from one another
    on a foreign key field

    Django doesnt support custom lookups by default, and this tests some
    of the overridden behavior
    """
    test_int_fk_model = ddf.G(models.TestTrigger, fk_field=None)

    # Protect a foreign key from being updated to a different value
    trigger = pgtrigger.Protect(
        name='test_is_distinct_from_condition_fk_field1',
        when=pgtrigger.Before,
        operation=pgtrigger.Update,
        condition=pgtrigger.Q(old__fk_field__df=pgtrigger.F('new__fk_field')),
    )
    with trigger.install(models.TestTrigger):
        with pytest.raises(InternalError, match='Cannot update rows'):
            test_int_fk_model.fk_field = User(id=1)
            test_int_fk_model.save()

        # Saving the same values should work fine
        test_int_fk_model.fk_field = None
        test_int_fk_model.save()

    # Protect a non-int foreign key from being updated to a different value
    char_pk = ddf.G(models.CharPk)
    test_char_fk_model = ddf.G(models.TestTrigger, char_pk_fk_field=char_pk)
    trigger = pgtrigger.Protect(
        name='test_is_distinct_from_condition_fk_field2',
        when=pgtrigger.Before,
        operation=pgtrigger.Update,
        condition=pgtrigger.Q(old__char_pk_fk_field__df=pgtrigger.F('new__char_pk_fk_field')),
    )
    with trigger.install(models.TestTrigger):
        with pytest.raises(InternalError, match='Cannot update rows'):
            test_char_fk_model.char_pk_fk_field = None
            test_char_fk_model.save()

        # Saving the same values should work fine
        test_char_fk_model.char_pk_fk_field = char_pk
        test_char_fk_model.save()


@pytest.mark.django_db(transaction=True)
def test_is_not_distinct_from_condition():
    """Tests triggers where the old and new are not distinct from one another

    Note that distinct is the not the same as not being equal since nulls
    are never equal
    """
    test_model = ddf.G(models.TestTrigger, int_field=0)

    # Protect a field from being updated to the same value. In this case,
    # both int_field and nullable need to change in order for the update to
    # happen
    trigger = pgtrigger.Protect(
        name='test_is_not_distinct_from_condition1',
        when=pgtrigger.Before,
        operation=pgtrigger.Update,
        condition=pgtrigger.Q(old__int_field__ndf=pgtrigger.F('new__int_field'))
        | pgtrigger.Q(old__nullable__ndf=pgtrigger.F('new__nullable')),
    )
    with trigger.install(models.TestTrigger):

        with pytest.raises(InternalError, match='Cannot update rows'):
            test_model.int_field = 1
            test_model.save()

        # Ensure the null case works
        with pytest.raises(InternalError, match='Cannot update rows'):
            test_model.int_field = 0
            test_model.nullable = '1'
            test_model.save()

        # Updating both fields will ignore the trigger
        test_model.int_field = 1
        test_model.nullable = '1'
        test_model.save()


def test_max_name_length(mocker):
    """
    Verifies that a trigger with the exact MAX_NAME_LENGTH can be installed
    fine. Also checks that going above this by one character results in
    a database error
    """
    # Protect a field from being updated to the same value. In this case,
    # both int_field and nullable need to change in order for the update to
    # happen
    trigger = pgtrigger.Protect(
        name='t' * core.MAX_NAME_LENGTH,
        operation=pgtrigger.Update,
    )
    assert trigger.get_pgid(models.TestTrigger)

    mocker.patch.object(pgtrigger.Protect, 'validate_name')
    with pytest.raises(ValueError):
        trigger = pgtrigger.Protect(
            name='a' * (core.MAX_NAME_LENGTH + 1),
            operation=pgtrigger.Update,
        )
        trigger.get_pgid(models.TestTrigger)


def test_invalid_name_characters(mocker):
    """
    Verifies that trigger names must contain only alphanumeric
    characters, hyphens, or underscores
    """
    pgtrigger.Protect(
        name='hello_world-111',
        operation=pgtrigger.Update,
    )
    with pytest.raises(ValueError, match="alphanumeric"):
        pgtrigger.Protect(
            name='hello.world',
            operation=pgtrigger.Update,
        )


@pytest.mark.django_db(transaction=True)
def test_complex_conditions():
    """Tests complex OLD and NEW trigger conditions"""
    zero_to_one = ddf.G(models.TestModel, int_field=0)

    # Dont let intfield go from 0 -> 1
    trigger = pgtrigger.Protect(
        name='test_complex_conditions1',
        when=pgtrigger.Before,
        operation=pgtrigger.Update,
        condition=pgtrigger.Q(old__int_field=0, new__int_field=1),
    )
    with trigger.install(models.TestModel):
        with pytest.raises(InternalError, match='Cannot update rows'):
            zero_to_one.int_field = 1
            zero_to_one.save()

    # Test a condition with a datetime field
    test_model = ddf.G(models.TestTrigger, int_field=0, dt_field=dt.datetime(2020, 1, 1))
    trigger = pgtrigger.Protect(
        name='test_complex_conditions2',
        when=pgtrigger.Before,
        operation=pgtrigger.Update,
        condition=(
            pgtrigger.Q(old__int_field=0, new__int_field=1)
            | pgtrigger.Q(new__dt_field__lt=dt.datetime(2020, 1, 1))
        ),
    )
    with trigger.install(models.TestTrigger):
        with pytest.raises(InternalError, match='Cannot update rows'):
            test_model.int_field = 1
            test_model.save()
        test_model.int_field = 2
        test_model.save()

        with pytest.raises(InternalError, match='Cannot update rows'):
            test_model.dt_field = dt.datetime(2019, 1, 1)
            test_model.save()


def test_referencing_rendering():
    """Verifies the rendering of the Referencing construct"""
    assert (
        str(pgtrigger.Referencing(old='old_table')).strip() == 'REFERENCING OLD TABLE AS old_table'
    )
    assert (
        str(pgtrigger.Referencing(new='new_table')).strip() == 'REFERENCING NEW TABLE AS new_table'
    )
    assert (
        str(pgtrigger.Referencing(old='old_table', new='new_table')).strip()
        == 'REFERENCING OLD TABLE AS old_table  NEW TABLE AS new_table'
    )


def test_arg_checks():
    """
    There are quite a few places that check arguments in the trigger module.
    Enumerate these cases here to make sure they work
    """

    with pytest.raises(ValueError, match='Must provide either "old" and/or "new"'):
        pgtrigger.Referencing()

    with pytest.raises(ValueError, match='Must provide SQL'):
        pgtrigger.Condition()

    with pytest.raises(ValueError, match='Must provide at least one'):
        pgtrigger.UpdateOf()

    with pytest.raises(ValueError, match='must have "name"'):
        pgtrigger.Trigger(when=pgtrigger.Before, operation=pgtrigger.Update)

    with pytest.raises(ValueError, match='Invalid "level"'):
        pgtrigger.Trigger(level='invalid')

    with pytest.raises(ValueError, match='Invalid "when"'):
        pgtrigger.Trigger(when='invalid')

    with pytest.raises(ValueError, match='Invalid "operation"'):
        pgtrigger.Trigger(when=pgtrigger.Before, operation='invalid')

    with pytest.raises(ValueError, match='Invalid "timing"'):
        pgtrigger.Trigger(when=pgtrigger.Before, operation=pgtrigger.Update, timing='timing')

    with pytest.raises(ValueError, match='Row-level triggers cannot have'):
        pgtrigger.Trigger(
            when=pgtrigger.Before,
            operation=pgtrigger.Update,
            referencing=pgtrigger.Referencing(old='old_table'),
        )

    with pytest.raises(ValueError, match='must have "level" attribute'):
        pgtrigger.Trigger(
            level=pgtrigger.Statement,
            when=pgtrigger.After,
            operation=pgtrigger.Update,
            timing=pgtrigger.Immediate,
        )

    with pytest.raises(ValueError, match='must have "when" attribute'):
        pgtrigger.Trigger(
            level=pgtrigger.Row,
            when=pgtrigger.Before,
            operation=pgtrigger.Update,
            timing=pgtrigger.Immediate,
        )

    with pytest.raises(ValueError, match='Must define func'):
        pgtrigger.Trigger(name='test', when=pgtrigger.Before, operation=pgtrigger.Update).get_func(
            None
        )

    with pytest.raises(ValueError, match='> 47'):
        pgtrigger.Trigger(when=pgtrigger.Before, operation=pgtrigger.Update, name='1' * 48).pgid


def test_operations():
    """Tests Operation objects and ORing them together"""
    assert str(pgtrigger.Update) == 'UPDATE'
    assert str(pgtrigger.UpdateOf('col1')) == 'UPDATE OF "col1"'
    assert str(pgtrigger.UpdateOf('c1', 'c2')) == 'UPDATE OF "c1", "c2"'

    assert str(pgtrigger.Update | pgtrigger.Delete) == 'UPDATE OR DELETE'
    assert (
        str(pgtrigger.Update | pgtrigger.Delete | pgtrigger.Insert) == 'UPDATE OR DELETE OR INSERT'
    )
    assert str(pgtrigger.Delete | pgtrigger.Update) == 'DELETE OR UPDATE'


@pytest.mark.django_db(transaction=True)
def test_custom_trigger_definitions():
    """Test a variety of custom trigger definitions"""
    test_model = ddf.G(models.TestTrigger)

    # Protect against inserts or updates
    # Note: Although we could use the "protect" trigger for this,
    # we manually provide the trigger code to test manual declarations
    trigger = pgtrigger.Trigger(
        name='test_custom_definition1',
        when=pgtrigger.Before,
        operation=pgtrigger.Insert | pgtrigger.Update,
        func="RAISE EXCEPTION 'no no no!';",
    )
    with trigger.install(test_model):

        # Inserts and updates are no longer available
        with pytest.raises(InternalError, match='no no no!'):
            models.TestTrigger.objects.create()

        with pytest.raises(InternalError, match='no no no!'):
            test_model.save()

    # Inserts and updates should work again
    ddf.G(models.TestTrigger)
    test_model.save()

    # Protect updates of a single column
    trigger = pgtrigger.Trigger(
        name='test_custom_definition2',
        when=pgtrigger.Before,
        operation=pgtrigger.UpdateOf('int_field'),
        func="RAISE EXCEPTION 'no no no!';",
    )
    with trigger.install(models.TestTrigger):
        # "field" should be able to be updated, but other_field should not
        test_model.save(update_fields=['field'])

        with pytest.raises(InternalError, match='no no no!'):
            test_model.save(update_fields=['int_field'])

    # Protect statement-level creates
    trigger = pgtrigger.Trigger(
        name='test_custom_definition3',
        level=pgtrigger.Statement,
        when=pgtrigger.Before,
        operation=pgtrigger.Update,
        func="RAISE EXCEPTION 'bad statement!';",
    )
    with trigger.install(models.TestTrigger):
        with pytest.raises(InternalError, match='bad statement!'):
            test_model.save()


@pytest.mark.django_db(transaction=True)
def test_trigger_conditions():
    """Tests triggers with custom conditions"""
    test_model = ddf.G(models.TestTrigger)

    # Protect against inserts only when "field" is "hello"
    trigger = pgtrigger.Trigger(
        name='test_condition1',
        when=pgtrigger.Before,
        operation=pgtrigger.Insert,
        func="RAISE EXCEPTION 'no no no!';",
        condition=pgtrigger.Q(new__field='hello'),
    )
    with trigger.install(test_model):
        ddf.G(models.TestTrigger, field='hi!')
        with pytest.raises(InternalError, match='no no no!'):
            models.TestTrigger.objects.create(field='hello')

    # Protect updates where nothing is actually updated
    trigger = pgtrigger.Trigger(
        name='test_condition2',
        when=pgtrigger.Before,
        operation=pgtrigger.Update,
        func="RAISE EXCEPTION 'no no no!';",
        condition=pgtrigger.Condition('OLD.* IS NOT DISTINCT FROM NEW.*'),
    )
    with trigger.install(test_model):
        test_model.int_field = test_model.int_field + 1
        test_model.save()

        # Saving the same fields again will cause an error
        with pytest.raises(InternalError, match='no no no!'):
            test_model.save()

    # Make a model readonly when the int_field is -1
    read_only = ddf.G(models.TestModel, int_field=-1)
    non_read_only = ddf.G(models.TestModel, int_field=-2)

    trigger = pgtrigger.Trigger(
        name='test_condition3',
        when=pgtrigger.Before,
        operation=pgtrigger.Update | pgtrigger.Delete,
        func="RAISE EXCEPTION 'no no no!';",
        condition=pgtrigger.Q(old__int_field=-1),
    )
    with trigger.install(models.TestModel):
        with pytest.raises(InternalError, match='no no no!'):
            read_only.save()

        with pytest.raises(InternalError, match='no no no!'):
            read_only.delete()

        non_read_only.save()
        non_read_only.delete()


@pytest.mark.django_db(databases=['default', 'other'], transaction=True)
@pytest.mark.order(-2)  # This is a leaky test that modifies the schema. Always run last
def test_trigger_management(mocker):
    """Verifies dropping and recreating triggers works"""
    deletion_protected_model = ddf.G(models.TestTrigger)

    # Triggers should be installed initially
    with pytest.raises(InternalError, match='Cannot delete rows'):
        deletion_protected_model.delete()

    # Deactivate triggers. Deletions should happen without issue.
    # Note: run twice for idempotency checks
    pgtrigger.disable()
    pgtrigger.disable()
    deletion_protected_model.delete()

    # Reactivate triggers. Deletions should be protected
    pgtrigger.enable()
    pgtrigger.enable()
    deletion_protected_model = ddf.G(models.TestTrigger)
    with pytest.raises(InternalError, match='Cannot delete rows'):
        deletion_protected_model.delete()

    # Do the same tests again, except this time uninstall and reinstall
    # triggers
    pgtrigger.uninstall()
    pgtrigger.uninstall()
    deletion_protected_model.delete()

    # Reactivate triggers. Deletions should be protected
    pgtrigger.install()
    pgtrigger.install()
    deletion_protected_model = ddf.G(models.TestTrigger)
    with pytest.raises(InternalError, match='Cannot delete rows'):
        deletion_protected_model.delete()

    # Pruning triggers should do nothing at the moment
    pgtrigger.prune()
    pgtrigger.prune()
    with pytest.raises(InternalError, match='Cannot delete rows'):
        deletion_protected_model.delete()

    # However, changing the trigger name will cause the old triggers to
    # be pruned
    mocker.patch(
        'pgtrigger.Protect.name',
        new_callable=mocker.PropertyMock,
        return_value='hi',
    )
    pgtrigger.prune()
    pgtrigger.prune()
    deletion_protected_model.delete()

"""Tests multi-database support"""

# flake8: noqa
import io
import contextlib

import ddf
from django.core.management import call_command
from django.db.utils import InternalError
import pytest

import pgtrigger
import pgtrigger.tests.models as test_models


class SchemaRouter:
    """
    A router to control tables that should be migrated to different schemas
    """

    def db_for_read(self, model, **hints):
        if model == test_models.OrderSchema:
            return 'order'
        elif model == test_models.ReceiptSchema:
            return 'receipt'
        return None

    def db_for_write(self, model, **hints):
        return self.db_for_read(model, **hints)


@pytest.fixture(autouse=True)
def routed_db(settings):
    settings.DATABASE_ROUTERS = ['pgtrigger.tests.test_multi_schema.SchemaRouter']


@pytest.fixture(autouse=True)
def schema_triggers():
    protect_deletes = pgtrigger.Protect(name="protect_deletes", operation=pgtrigger.Delete)
    protect_updates = pgtrigger.Protect(name="protect_updates", operation=pgtrigger.Update)

    with contextlib.ExitStack() as contexts:
        contexts.enter_context(protect_deletes.register(test_models.OrderSchema))
        contexts.enter_context(protect_deletes.install(test_models.OrderSchema))
        contexts.enter_context(protect_updates.register(test_models.ReceiptSchema))
        contexts.enter_context(protect_updates.install(test_models.ReceiptSchema))

        yield


@pytest.mark.django_db(databases=["order", "receipt"], transaction=True)
def test_multi_schema_triggers_work():
    """Verify the triggers in the schema_triggers fixture work"""
    order = ddf.G("tests.OrderSchema")
    receipt = ddf.G("tests.ReceiptSchema")

    with pytest.raises(InternalError, match="Cannot delete"):
        order.delete()

    with pytest.raises(InternalError, match="Cannot update"):
        receipt.char_field = "hello"
        receipt.save()

    receipt.delete()

    order = ddf.G("tests.OrderSchema")
    with pgtrigger.ignore("tests.OrderSchema:protect_deletes"):
        order.delete()


@pytest.mark.django_db(databases=["order", "receipt", "default", "other"], transaction=True)
def test_commands(capsys):
    """Verify commands work"""
    call_command('pgtrigger', 'install')
    call_command('pgtrigger', 'ls')
    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    expected_lines = [
        'tests.CustomSoftDelete:soft_delete\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.CustomTableName:protect_delete\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.FSM:fsm\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.OrderSchema:protect_deletes\torder\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ReceiptSchema:protect_updates\treceipt\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.SearchModel:add_body_title_to_vector\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.SearchModel:add_body_to_vector\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.SoftDelete:soft_delete\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.TestDefaultThrough:protect_it\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.TestTrigger:protect_misc_insert\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.TestTriggerProxy:protect_delete\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ToLogModel:after_update_row_test\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ToLogModel:after_update_statement_test\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ToLogModel:update_of_statement_test\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
    ]
    assert set(expected_lines).issubset(set(lines))

    call_command('pgtrigger', 'ls', '-d', 'receipt', '-d', 'order')
    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    expected_lines = [
        '',
        'tests.OrderSchema:protect_deletes\torder\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ReceiptSchema:protect_updates\treceipt\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
    ]
    assert set(expected_lines) == set(lines)

    # Installed a trigger to be pruned. Note that this will leak into other tests if
    # we fail before pruning it
    protect_inserts = pgtrigger.Protect(name="protect_inserts", operation=pgtrigger.Insert)
    protect_inserts.install(test_models.OrderSchema)

    call_command('pgtrigger', 'ls', '-d', 'receipt', '-d', 'order')
    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    expected_lines = [
        '',
        'tests.OrderSchema:protect_deletes\torder\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ReceiptSchema:protect_updates\treceipt\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests_orderschema:pgtrigger_protect_inserts_a0767\torder\t\x1b[96mPRUNE\x1b[0m\t\x1b[92mENABLED\x1b[0m',
    ]
    assert set(expected_lines) == set(lines)

    call_command('pgtrigger', 'prune', '-d', 'order', '-d', 'receipt')
    call_command('pgtrigger', 'ls', '-d', 'receipt', '-d', 'order')
    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    expected_lines = [
        '',
        'tests.OrderSchema:protect_deletes\torder\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ReceiptSchema:protect_updates\treceipt\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
    ]
    assert set(expected_lines) == set(lines)

    # Set the search path to a schema.
    call_command('pgtrigger', 'ls', '-d', 'receipt', '-d', 'order', '-s', 'order')
    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    expected_lines = [
        '',
        'tests.OrderSchema:protect_deletes\torder\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ReceiptSchema:protect_updates\treceipt\t\x1b[91mUNINSTALLED\x1b[0m',
    ]
    assert set(expected_lines) == set(lines)

    # Use both schemas. Everything should be installed
    call_command('pgtrigger', 'ls', '-d', 'receipt', '-d', 'order', '-s', 'order', '-s', 'receipt')
    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    expected_lines = [
        '',
        'tests.OrderSchema:protect_deletes\torder\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ReceiptSchema:protect_updates\treceipt\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
    ]
    assert set(expected_lines) == set(lines)

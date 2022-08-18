"""Tests multi-database support"""

# flake8: noqa

import contextlib

import ddf
from django.core.management import call_command
from django.db.utils import InternalError
import pytest

import pgtrigger
from pgtrigger.tests import models


class SchemaRouter:
    """
    A router to control tables that should be migrated to different schemas
    """

    def db_for_read(self, model, **hints):
        if model == models.OrderSchema:
            return 'order'
        elif model == models.ReceiptSchema:  # pragma: no branch
            return 'receipt'

    def db_for_write(self, model, **hints):
        return self.db_for_read(model, **hints)

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if model_name == 'orderschema':
            return db == 'order'
        elif model_name == 'receiptschema':
            return db == 'receipt'


@pytest.fixture(autouse=True)
def routed_db(settings):
    settings.DATABASE_ROUTERS = [
        'pgtrigger.tests.test_multi_schema.SchemaRouter',
        'pgtrigger.tests.models.Router',
    ]


@pytest.fixture(autouse=True)
def schema_triggers():
    protect_deletes = pgtrigger.Protect(name="protect_deletes", operation=pgtrigger.Delete)
    protect_updates = pgtrigger.Protect(name="protect_updates", operation=pgtrigger.Update)

    with contextlib.ExitStack() as stack:
        stack.enter_context(protect_deletes.register(models.OrderSchema))
        stack.enter_context(protect_updates.register(models.ReceiptSchema))

        yield


@pytest.mark.django_db(databases=["order", "receipt"], transaction=True)
def test_multi_schema_triggers_work():
    """Verify the triggers in the schema_triggers fixture work"""
    call_command('pgtrigger', 'install', '-d', 'order')
    call_command('pgtrigger', 'install', '-d', 'receipt')

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
    call_command('pgtrigger', 'ls')
    lines = capsys.readouterr().out.split('\n')
    expected_lines = [
        '',
        '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.CustomSoftDelete:soft_delete',
        '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.CustomTableName:protect_delete',
        '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.FSM:fsm',
        '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.SearchModel:add_body_title_to_vector',
        '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.SearchModel:add_body_to_vector',
        '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.SoftDelete:soft_delete',
        '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.TestDefaultThrough:protect_it',
        '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.TestTrigger:protect_misc_insert',
        '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.TestTriggerProxy:protect_delete',
        '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.ToLogModel:after_update_row_test',
        '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.ToLogModel:after_update_statement_test',
        '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.ToLogModel:update_of_statement_test',
        '\x1b[94mUNALLOWED\x1b[0m \x1b[94mN/A\x1b[0m     tests.OrderSchema:protect_deletes',
        '\x1b[94mUNALLOWED\x1b[0m \x1b[94mN/A\x1b[0m     tests.ReceiptSchema:protect_updates',
    ]
    assert set(expected_lines).issubset(set(lines))

    call_command('pgtrigger', 'ls', '-d', 'receipt')
    lines = capsys.readouterr().out.split('\n')
    expected_lines = [
        '',
        '\x1b[91mUNINSTALLED\x1b[0m \x1b[94mN/A\x1b[0m     tests.ReceiptSchema:protect_updates',
        '\x1b[92mINSTALLED\x1b[0m   \x1b[92mENABLED\x1b[0m tests.CustomSoftDelete:soft_delete',
        '\x1b[92mINSTALLED\x1b[0m   \x1b[92mENABLED\x1b[0m tests.CustomTableName:protect_delete',
        '\x1b[92mINSTALLED\x1b[0m   \x1b[92mENABLED\x1b[0m tests.FSM:fsm',
        '\x1b[92mINSTALLED\x1b[0m   \x1b[92mENABLED\x1b[0m tests.SearchModel:add_body_title_to_vector',
        '\x1b[92mINSTALLED\x1b[0m   \x1b[92mENABLED\x1b[0m tests.SearchModel:add_body_to_vector',
        '\x1b[92mINSTALLED\x1b[0m   \x1b[92mENABLED\x1b[0m tests.SoftDelete:soft_delete',
        '\x1b[92mINSTALLED\x1b[0m   \x1b[92mENABLED\x1b[0m tests.TestDefaultThrough:protect_it',
        '\x1b[92mINSTALLED\x1b[0m   \x1b[92mENABLED\x1b[0m tests.TestTrigger:protect_misc_insert',
        '\x1b[92mINSTALLED\x1b[0m   \x1b[92mENABLED\x1b[0m tests.TestTriggerProxy:protect_delete',
        '\x1b[92mINSTALLED\x1b[0m   \x1b[92mENABLED\x1b[0m tests.ToLogModel:after_update_row_test',
        '\x1b[92mINSTALLED\x1b[0m   \x1b[92mENABLED\x1b[0m tests.ToLogModel:after_update_statement_test',
        '\x1b[92mINSTALLED\x1b[0m   \x1b[92mENABLED\x1b[0m tests.ToLogModel:update_of_statement_test',
        '\x1b[94mUNALLOWED\x1b[0m   \x1b[94mN/A\x1b[0m     tests.OrderSchema:protect_deletes',
    ]
    assert set(expected_lines).issubset(set(lines))

    call_command('pgtrigger', 'install', '-d', 'receipt')
    call_command('pgtrigger', 'ls', '-d', 'receipt')
    lines = capsys.readouterr().out.split('\n')
    expected_lines = [
        '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.ReceiptSchema:protect_updates',
    ]
    assert set(expected_lines).issubset(set(lines))

    # Installed a trigger to be pruned.
    protect_inserts = pgtrigger.Protect(name="protect_inserts", operation=pgtrigger.Insert)
    protect_inserts.install(models.OrderSchema, database='order')

    call_command('pgtrigger', 'ls', '-d', 'order')
    lines = capsys.readouterr().out.split('\n')
    expected_lines = [
        '\x1b[91mUNINSTALLED\x1b[0m \x1b[94mN/A\x1b[0m     tests.OrderSchema:protect_deletes',
        '\x1b[94mUNALLOWED\x1b[0m   \x1b[94mN/A\x1b[0m     tests.ReceiptSchema:protect_updates',
        '\x1b[96mPRUNE\x1b[0m       \x1b[92mENABLED\x1b[0m tests_orderschema:pgtrigger_protect_inserts_a0767',
    ]
    assert set(expected_lines).issubset(set(lines))

    call_command('pgtrigger', 'prune', '-d', 'order')
    call_command('pgtrigger', 'install', '-d', 'order')
    call_command('pgtrigger', 'ls', '-d', 'order')
    lines = capsys.readouterr().out.split('\n')
    for line in lines:
        assert 'PRUNE' not in line
    expected_lines = [
        '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.OrderSchema:protect_deletes',
        '\x1b[94mUNALLOWED\x1b[0m \x1b[94mN/A\x1b[0m     tests.ReceiptSchema:protect_updates',
    ]
    assert set(expected_lines).issubset(set(lines))

    # Set the search path to a schema and check results
    call_command('pgtrigger', 'uninstall', '-s', 'receipt')
    call_command('pgtrigger', 'ls', 'tests.CustomSoftDelete:soft_delete', '-s', 'receipt')
    lines = capsys.readouterr().out.split('\n')
    expected_lines = [
        '',
        '\x1b[91mUNINSTALLED\x1b[0m \x1b[94mN/A\x1b[0m tests.CustomSoftDelete:soft_delete',
    ]
    assert set(expected_lines) == set(lines)

    call_command('pgtrigger', 'install', 'tests.CustomSoftDelete:soft_delete', '-s', 'receipt')
    call_command('pgtrigger', 'ls', 'tests.CustomSoftDelete:soft_delete', '-s', 'receipt')
    lines = capsys.readouterr().out.split('\n')
    expected_lines = [
        '',
        '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.CustomSoftDelete:soft_delete',
    ]
    assert set(expected_lines) == set(lines)

"""Tests multi-database support"""
# flake8: noqa

import contextlib

import ddf
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import transaction
from django.db.utils import InternalError
import pytest

import pgtrigger
from pgtrigger.tests import models


class ToLogRouter:
    """
    Route the "ToLog" model to the "other" database
    """

    route_app_labels = {'auth', 'contenttypes'}

    def db_for_write(self, model, **hints):
        if model == models.ToLogModel:
            return 'other'

        return None


@pytest.fixture
def routed_db(settings):
    settings.DATABASE_ROUTERS = ['pgtrigger.tests.test_multi_db.ToLogRouter']
    call_command('pgtrigger', 'install')


@pytest.fixture(autouse=True)
def auto_ignore_schema_databases_and_route(ignore_schema_databases, routed_db):
    """Setup DBs and routing"""
    pass


@pytest.mark.django_db(databases=["default", "sqlite", "other"], transaction=True)
def test_multi_db_ignore():
    """Tests ignoring triggers across multiple databases"""
    trigger = pgtrigger.Protect(operation=pgtrigger.Delete, name="protect_deletes")

    with contextlib.ExitStack() as contexts:
        contexts.enter_context(trigger.register(models.ToLogModel))
        contexts.enter_context(trigger.register(User))
        contexts.enter_context(trigger.install(models.ToLogModel))
        contexts.enter_context(trigger.install(User))

        with pytest.raises(InternalError, match="Cannot delete"):
            log = ddf.G(models.ToLogModel)
            log.delete()

        with pytest.raises(InternalError, match="Cannot delete"):
            user = ddf.G(User)
            user.delete()

        with transaction.atomic():
            with pgtrigger.ignore("tests.ToLogModel:protect_deletes", "auth.User:protect_deletes"):
                log = models.ToLogModel.objects.create()
                log.delete()
                user = ddf.G(User)
                user.delete()

            with pytest.raises(InternalError, match="Cannot delete"):
                user = User.objects.create(username="hi")
                user.delete()

            with pytest.raises(InternalError, match="Cannot delete"):
                log = models.ToLogModel.objects.create()
                log.delete()


@pytest.mark.django_db(databases=["default", "sqlite", "other"])
def test_full_ls(capsys):
    call_command('pgtrigger', 'ls')
    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    expected_lines = [
        'tests.CustomSoftDelete:soft_delete\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.CustomTableName:protect_delete\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.FSM:fsm\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.SoftDelete:soft_delete\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.TestDefaultThrough:protect_it\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.TestTrigger:protect_misc_insert\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.TestTriggerProxy:protect_delete\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ToLogModel:after_update_row_test\tother\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ToLogModel:after_update_statement_test\tother\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ToLogModel:update_of_statement_test\tother\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
    ]
    assert set(expected_lines).issubset(set(lines))


@pytest.mark.django_db(databases=["default", "sqlite", "other"])
def test_single_db_enable(capsys):
    call_command('pgtrigger', 'disable')
    call_command('pgtrigger', 'enable', '--database', 'other')

    call_command('pgtrigger', 'ls')
    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    expected_lines = [
        '',
        'tests.CustomSoftDelete:soft_delete\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[91mDISABLED\x1b[0m',
        'tests.CustomTableName:protect_delete\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[91mDISABLED\x1b[0m',
        'tests.FSM:fsm\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[91mDISABLED\x1b[0m',
        'tests.SoftDelete:soft_delete\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[91mDISABLED\x1b[0m',
        'tests.TestDefaultThrough:protect_it\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[91mDISABLED\x1b[0m',
        'tests.TestTrigger:protect_misc_insert\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[91mDISABLED\x1b[0m',
        'tests.TestTriggerProxy:protect_delete\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[91mDISABLED\x1b[0m',
        'tests.ToLogModel:after_update_row_test\tother\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ToLogModel:after_update_statement_test\tother\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ToLogModel:update_of_statement_test\tother\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
    ]
    assert set(expected_lines).issubset(set(lines))


@pytest.mark.django_db(databases=["default", "sqlite", "other"])
def test_single_db_disable(capsys):
    call_command('pgtrigger', 'disable', '--database', 'other')
    call_command('pgtrigger', 'ls')
    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    expected_lines = [
        '',
        'tests.CustomSoftDelete:soft_delete\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.CustomTableName:protect_delete\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.FSM:fsm\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.SoftDelete:soft_delete\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.TestDefaultThrough:protect_it\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.TestTrigger:protect_misc_insert\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.TestTriggerProxy:protect_delete\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ToLogModel:after_update_row_test\tother\t\x1b[92mINSTALLED\x1b[0m\t\x1b[91mDISABLED\x1b[0m',
        'tests.ToLogModel:after_update_statement_test\tother\t\x1b[92mINSTALLED\x1b[0m\t\x1b[91mDISABLED\x1b[0m',
        'tests.ToLogModel:update_of_statement_test\tother\t\x1b[92mINSTALLED\x1b[0m\t\x1b[91mDISABLED\x1b[0m',
    ]
    assert set(expected_lines).issubset(set(lines))


@pytest.mark.django_db(databases=["default", "sqlite", "other"])
def test_single_db_ls(capsys):
    """Only list a single database"""
    call_command('pgtrigger', 'ls', '--database', 'other')
    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    expected_lines = [
        '',
        'tests.ToLogModel:after_update_row_test\tother\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ToLogModel:after_update_statement_test\tother\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ToLogModel:update_of_statement_test\tother\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
    ]
    assert set(expected_lines).issubset(set(lines))


@pytest.mark.django_db(databases=["default", "sqlite", "other"])
def test_single_db_uninstall(capsys):
    """Uninstall a single database and verify results"""
    call_command('pgtrigger', 'uninstall', '--database', 'default')
    call_command('pgtrigger', 'ls')
    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    expected_lines = [
        '',
        'tests.CustomSoftDelete:soft_delete\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
        'tests.CustomTableName:protect_delete\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
        'tests.FSM:fsm\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
        'tests.SoftDelete:soft_delete\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
        'tests.TestDefaultThrough:protect_it\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
        'tests.TestTrigger:protect_misc_insert\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
        'tests.TestTriggerProxy:protect_delete\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
        'tests.ToLogModel:after_update_row_test\tother\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ToLogModel:after_update_statement_test\tother\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ToLogModel:update_of_statement_test\tother\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
    ]
    assert set(expected_lines).issubset(set(lines))


@pytest.mark.django_db(databases=["default", "sqlite", "other"])
def test_single_db_install(capsys):
    """Install a single database and verify results"""
    call_command('pgtrigger', 'uninstall')
    call_command('pgtrigger', 'install', '--database', 'other')
    call_command('pgtrigger', 'ls')
    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    expected_lines = [
        '',
        'tests.CustomSoftDelete:soft_delete\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
        'tests.CustomTableName:protect_delete\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
        'tests.FSM:fsm\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
        'tests.SoftDelete:soft_delete\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
        'tests.TestDefaultThrough:protect_it\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
        'tests.TestTrigger:protect_misc_insert\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
        'tests.TestTriggerProxy:protect_delete\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
        'tests.ToLogModel:after_update_row_test\tother\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ToLogModel:after_update_statement_test\tother\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
        'tests.ToLogModel:update_of_statement_test\tother\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
    ]
    assert set(expected_lines).issubset(set(lines))

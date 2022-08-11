"""Tests multi-database support"""

import contextlib
import io
import sys

import ddf
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import transaction
from django.db.utils import InternalError
import pytest

import pgtrigger
import pgtrigger.tests.models as test_models


@contextlib.contextmanager
def capture_stdout():
    old_stdout = sys.stdout
    sys.stdout = out = io.StringIO()
    try:
        yield out
    finally:
        sys.stdout = old_stdout


class ToLogRouter:
    """
    Route the "ToLog" model to the "other" database
    """

    route_app_labels = {'auth', 'contenttypes'}

    def db_for_write(self, model, **hints):
        if model == test_models.ToLogModel:
            return 'other'

        return None


@pytest.fixture
def routed_db(settings):
    settings.DATABASE_ROUTERS = ['pgtrigger.tests.test_multi_db.ToLogRouter']
    call_command('pgtrigger', 'install')


@pytest.mark.usefixtures("routed_db")
@pytest.mark.django_db(databases=["default", "sqlite", "other"], transaction=True)
def test_multi_db_ignore():
    """Tests ignoring triggers across multiple databases"""
    trigger = pgtrigger.Protect(operation=pgtrigger.Delete, name="protect_deletes")

    with contextlib.ExitStack() as contexts:
        contexts.enter_context(trigger.register(test_models.ToLogModel))
        contexts.enter_context(trigger.register(User))
        contexts.enter_context(trigger.install(test_models.ToLogModel))
        contexts.enter_context(trigger.install(User))

        with pytest.raises(InternalError, match="Cannot delete"):
            log = ddf.G(test_models.ToLogModel)
            log.delete()

        with pytest.raises(InternalError, match="Cannot delete"):
            user = ddf.G(User)
            user.delete()

        with transaction.atomic():
            with pgtrigger.ignore("tests.ToLogModel:protect_deletes", "auth.User:protect_deletes"):
                log = test_models.ToLogModel.objects.create()
                log.delete()
                user = ddf.G(User)
                user.delete()

            with pytest.raises(InternalError, match="Cannot delete"):
                user = User.objects.create(username="hi")
                user.delete()

            with pytest.raises(InternalError, match="Cannot delete"):
                log = test_models.ToLogModel.objects.create()
                log.delete()


@pytest.mark.usefixtures("routed_db")
@pytest.mark.django_db(databases=["default", "sqlite", "other"])
def test_full_ls():
    with capture_stdout() as captured:
        call_command('pgtrigger', 'ls')
        lines = sorted(captured.getvalue().split('\n'))
        expected_lines = [
            'tests.CustomSoftDelete:soft_delete'
            '\tdefault'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.CustomTableName:protect_delete'
            '\tdefault'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.FSM:fsm\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
            'tests.SoftDelete:soft_delete'
            '\tdefault'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.TestDefaultThrough:protect_it'
            '\tdefault'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.TestTrigger:protect_misc_insert'
            '\tdefault'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.TestTriggerProxy:protect_delete'
            '\tdefault'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.ToLogModel:after_update_row_test'
            '\tother'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.ToLogModel:after_update_statement_test'
            '\tother'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.ToLogModel:update_of_statement_test'
            '\tother'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
        ]
        assert set(expected_lines).issubset(set(lines))


@pytest.mark.usefixtures("routed_db")
@pytest.mark.django_db(databases=["default", "sqlite", "other"])
def test_single_db_enable():
    call_command('pgtrigger', 'disable')
    call_command('pgtrigger', 'enable', '--database', 'other')

    with capture_stdout() as captured:
        call_command('pgtrigger', 'ls')
        lines = sorted(captured.getvalue().split('\n'))
        expected_lines = [
            '',
            'tests.CustomSoftDelete:soft_delete'
            '\tdefault'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[91mDISABLED\x1b[0m',
            'tests.CustomTableName:protect_delete'
            '\tdefault'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[91mDISABLED\x1b[0m',
            'tests.FSM:fsm\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[91mDISABLED\x1b[0m',
            'tests.SoftDelete:soft_delete'
            '\tdefault'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[91mDISABLED\x1b[0m',
            'tests.TestDefaultThrough:protect_it'
            '\tdefault'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[91mDISABLED\x1b[0m',
            'tests.TestTrigger:protect_misc_insert'
            '\tdefault'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[91mDISABLED\x1b[0m',
            'tests.TestTriggerProxy:protect_delete'
            '\tdefault'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[91mDISABLED\x1b[0m',
            'tests.ToLogModel:after_update_row_test'
            '\tother'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.ToLogModel:after_update_statement_test'
            '\tother'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.ToLogModel:update_of_statement_test'
            '\tother'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
        ]
        assert set(expected_lines).issubset(set(lines))


@pytest.mark.usefixtures("routed_db")
@pytest.mark.django_db(databases=["default", "sqlite", "other"])
def test_single_db_disable():
    call_command('pgtrigger', 'disable', '--database', 'other')

    with capture_stdout() as captured:
        call_command('pgtrigger', 'ls')
        lines = sorted(captured.getvalue().split('\n'))
        expected_lines = [
            '',
            'tests.CustomSoftDelete:soft_delete'
            '\tdefault'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.CustomTableName:protect_delete'
            '\tdefault'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.FSM:fsm\tdefault\t\x1b[92mINSTALLED\x1b[0m\t\x1b[92mENABLED\x1b[0m',
            'tests.SoftDelete:soft_delete'
            '\tdefault'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.TestDefaultThrough:protect_it'
            '\tdefault'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.TestTrigger:protect_misc_insert'
            '\tdefault'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.TestTriggerProxy:protect_delete'
            '\tdefault'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.ToLogModel:after_update_row_test'
            '\tother'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[91mDISABLED\x1b[0m',
            'tests.ToLogModel:after_update_statement_test'
            '\tother'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[91mDISABLED\x1b[0m',
            'tests.ToLogModel:update_of_statement_test'
            '\tother'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[91mDISABLED\x1b[0m',
        ]
        assert set(expected_lines).issubset(set(lines))


@pytest.mark.usefixtures("routed_db")
@pytest.mark.django_db(databases=["default", "sqlite", "other"])
def test_single_db_ls():
    """Only list a single database"""
    with capture_stdout() as captured:
        call_command('pgtrigger', 'ls', '--database', 'other')
        lines = sorted(captured.getvalue().split('\n'))
        expected_lines = [
            '',
            'tests.ToLogModel:after_update_row_test'
            '\tother'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.ToLogModel:after_update_statement_test'
            '\tother'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.ToLogModel:update_of_statement_test'
            '\tother'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
        ]
        assert set(expected_lines).issubset(set(lines))


@pytest.mark.usefixtures("routed_db")
@pytest.mark.django_db(databases=["default", "sqlite", "other"])
def test_single_db_uninstall():
    """Uninstall a single database and verify results"""
    call_command('pgtrigger', 'uninstall', '--database', 'default')

    with capture_stdout() as captured:
        call_command('pgtrigger', 'ls')
        lines = sorted(captured.getvalue().split('\n'))
        expected_lines = [
            '',
            'tests.CustomSoftDelete:soft_delete\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
            'tests.CustomTableName:protect_delete\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
            'tests.FSM:fsm\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
            'tests.SoftDelete:soft_delete\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
            'tests.TestDefaultThrough:protect_it\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
            'tests.TestTrigger:protect_misc_insert\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
            'tests.TestTriggerProxy:protect_delete\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
            'tests.ToLogModel:after_update_row_test'
            '\tother'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.ToLogModel:after_update_statement_test'
            '\tother'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.ToLogModel:update_of_statement_test'
            '\tother'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
        ]
        assert set(expected_lines).issubset(set(lines))


@pytest.mark.usefixtures("routed_db")
@pytest.mark.django_db(databases=["default", "sqlite", "other"])
def test_single_db_install():
    """Install a single database and verify results"""
    call_command('pgtrigger', 'uninstall')
    call_command('pgtrigger', 'install', '--database', 'other')

    with capture_stdout() as captured:
        call_command('pgtrigger', 'ls')
        lines = sorted(captured.getvalue().split('\n'))
        expected_lines = [
            '',
            'tests.CustomSoftDelete:soft_delete\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
            'tests.CustomTableName:protect_delete\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
            'tests.FSM:fsm\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
            'tests.SoftDelete:soft_delete\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
            'tests.TestDefaultThrough:protect_it\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
            'tests.TestTrigger:protect_misc_insert\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
            'tests.TestTriggerProxy:protect_delete\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
            'tests.ToLogModel:after_update_row_test'
            '\tother'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.ToLogModel:after_update_statement_test'
            '\tother'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
            'tests.ToLogModel:update_of_statement_test'
            '\tother'
            '\t\x1b[92mINSTALLED\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m',
        ]
        assert set(expected_lines).issubset(set(lines))


def test_invalid_args():
    with pytest.raises(ValueError):
        pgtrigger.get('uri', database='other')

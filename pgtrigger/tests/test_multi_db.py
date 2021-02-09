"""Tests multi-database support"""

import contextlib
import io
import sys

from django.core.management import call_command
import django.test

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
        """
        Attempts to write auth and contenttypes models go to auth_db.
        """
        if model == test_models.ToLogModel:
            return 'other'
        return None


@django.test.override_settings(
    DATABASE_ROUTERS=['pgtrigger.tests.test_multi_db.ToLogRouter']
)
class MultiDB(django.test.TestCase):
    databases = ['default', 'other']

    def setUp(self):
        # Trigger installation is originally executed during
        # test case setup, before any settings are overridden. Uninstall
        # and re-install all triggers to make sure they are properly installed.
        # Doing so also ensures that pruning across mutliple databases works
        with self.settings(
            DATABASE_ROUTERS=['pgtrigger.tests.test_multi_db.ToLogRouter']
        ):
            call_command('pgtrigger', 'uninstall')
            call_command('pgtrigger', 'install')

    def test_full_ls(self):
        with capture_stdout() as captured:
            call_command('pgtrigger', 'ls')
            lines = sorted(captured.getvalue().split('\n'))
            assert lines == [
                '',
                'tests.CustomSoftDelete:soft_delete'
                '\tdefault'
                '\t\x1b[92mINSTALLED\x1b[0m'
                '\t\x1b[92mENABLED\x1b[0m',
                'tests.FSM:fsm'
                '\tdefault'
                '\t\x1b[92mINSTALLED\x1b[0m'
                '\t\x1b[92mENABLED\x1b[0m',
                'tests.SoftDelete:soft_delete'
                '\tdefault'
                '\t\x1b[92mINSTALLED\x1b[0m'
                '\t\x1b[92mENABLED\x1b[0m',
                'tests.TestTrigger:protect_delete'
                '\tdefault'
                '\t\x1b[92mINSTALLED\x1b[0m'
                '\t\x1b[92mENABLED\x1b[0m',
                'tests.TestTrigger:protect_misc_insert'
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

    def test_single_db_enable(self):
        call_command('pgtrigger', 'disable')
        call_command('pgtrigger', 'enable', '--database', 'other')

        with capture_stdout() as captured:
            call_command('pgtrigger', 'ls')
            lines = sorted(captured.getvalue().split('\n'))
            assert lines == [
                '',
                'tests.CustomSoftDelete:soft_delete'
                '\tdefault'
                '\t\x1b[92mINSTALLED\x1b[0m'
                '\t\x1b[91mDISABLED\x1b[0m',
                'tests.FSM:fsm'
                '\tdefault'
                '\t\x1b[92mINSTALLED\x1b[0m'
                '\t\x1b[91mDISABLED\x1b[0m',
                'tests.SoftDelete:soft_delete'
                '\tdefault'
                '\t\x1b[92mINSTALLED\x1b[0m'
                '\t\x1b[91mDISABLED\x1b[0m',
                'tests.TestTrigger:protect_delete'
                '\tdefault'
                '\t\x1b[92mINSTALLED\x1b[0m'
                '\t\x1b[91mDISABLED\x1b[0m',
                'tests.TestTrigger:protect_misc_insert'
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

    def test_single_db_disable(self):
        call_command('pgtrigger', 'disable', '--database', 'other')

        with capture_stdout() as captured:
            call_command('pgtrigger', 'ls')
            lines = sorted(captured.getvalue().split('\n'))
            assert lines == [
                '',
                'tests.CustomSoftDelete:soft_delete'
                '\tdefault'
                '\t\x1b[92mINSTALLED\x1b[0m'
                '\t\x1b[92mENABLED\x1b[0m',
                'tests.FSM:fsm'
                '\tdefault'
                '\t\x1b[92mINSTALLED\x1b[0m'
                '\t\x1b[92mENABLED\x1b[0m',
                'tests.SoftDelete:soft_delete'
                '\tdefault'
                '\t\x1b[92mINSTALLED\x1b[0m'
                '\t\x1b[92mENABLED\x1b[0m',
                'tests.TestTrigger:protect_delete'
                '\tdefault'
                '\t\x1b[92mINSTALLED\x1b[0m'
                '\t\x1b[92mENABLED\x1b[0m',
                'tests.TestTrigger:protect_misc_insert'
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

    def test_single_db_ls(self):
        """Only list a single database"""
        with capture_stdout() as captured:
            call_command('pgtrigger', 'ls', '--database', 'other')
            lines = sorted(captured.getvalue().split('\n'))
            assert lines == [
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

    def test_single_db_uninstall(self):
        """Uninstall a single database and verify results"""
        call_command('pgtrigger', 'uninstall', '--database', 'default')

        with capture_stdout() as captured:
            call_command('pgtrigger', 'ls')
            lines = sorted(captured.getvalue().split('\n'))
            assert lines == [
                '',
                'tests.CustomSoftDelete:soft_delete'
                '\tdefault'
                '\t\x1b[91mUNINSTALLED\x1b[0m',
                'tests.FSM:fsm' '\tdefault' '\t\x1b[91mUNINSTALLED\x1b[0m',
                'tests.SoftDelete:soft_delete'
                '\tdefault'
                '\t\x1b[91mUNINSTALLED\x1b[0m',
                'tests.TestTrigger:protect_delete'
                '\tdefault'
                '\t\x1b[91mUNINSTALLED\x1b[0m',
                'tests.TestTrigger:protect_misc_insert'
                '\tdefault'
                '\t\x1b[91mUNINSTALLED\x1b[0m',
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

    def test_single_db_install(self):
        """Install a single database and verify results"""
        call_command('pgtrigger', 'uninstall')
        call_command('pgtrigger', 'install', '--database', 'other')

        with capture_stdout() as captured:
            call_command('pgtrigger', 'ls')
            lines = sorted(captured.getvalue().split('\n'))
            assert lines == [
                '',
                'tests.CustomSoftDelete:soft_delete'
                '\tdefault'
                '\t\x1b[91mUNINSTALLED\x1b[0m',
                'tests.FSM:fsm' '\tdefault' '\t\x1b[91mUNINSTALLED\x1b[0m',
                'tests.SoftDelete:soft_delete'
                '\tdefault'
                '\t\x1b[91mUNINSTALLED\x1b[0m',
                'tests.TestTrigger:protect_delete'
                '\tdefault'
                '\t\x1b[91mUNINSTALLED\x1b[0m',
                'tests.TestTrigger:protect_misc_insert'
                '\tdefault'
                '\t\x1b[91mUNINSTALLED\x1b[0m',
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

    def test_invalid_args(self):
        with self.assertRaises(ValueError):
            pgtrigger.get('uri', database='other')

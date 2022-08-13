# flake8: noqa
from unittest import mock

from django.core.management import call_command
import pytest

import pgtrigger
from pgtrigger import registry


@pytest.mark.django_db
def test_full_ls(capsys):
    """Tests listing all triggers"""

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
    ]
    assert set(expected_lines).issubset(set(lines))


@pytest.mark.django_db
def test_subset_ls(capsys):
    """Tests listing some triggers"""

    call_command(
        'pgtrigger',
        'ls',
        'tests.SoftDelete:soft_delete',
        'tests.TestTriggerProxy:protect_delete',
    )

    lines = capsys.readouterr().out.split('\n')
    assert set(lines) == set(
        [
            '',
            '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.SoftDelete:soft_delete',
            '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.TestTriggerProxy:protect_delete',
        ]
    )


@pytest.mark.django_db
def test_main_commands(capsys):
    """
    Tests running main commands
    """

    call_command('pgtrigger', 'uninstall')
    call_command(
        'pgtrigger',
        'ls',
        'tests.SoftDelete:soft_delete',
        'tests.TestTriggerProxy:protect_delete',
    )

    lines = capsys.readouterr().out.split('\n')
    assert set(lines) == set(
        [
            '',
            '\x1b[91mUNINSTALLED\x1b[0m \x1b[94mN/A\x1b[0m tests.SoftDelete:soft_delete',
            '\x1b[91mUNINSTALLED\x1b[0m \x1b[94mN/A\x1b[0m tests.TestTriggerProxy:protect_delete',
        ]
    )

    call_command('pgtrigger', 'install')
    call_command(
        'pgtrigger',
        'ls',
        'tests.SoftDelete:soft_delete',
        'tests.TestTriggerProxy:protect_delete',
    )

    lines = capsys.readouterr().out.split('\n')
    assert set(lines) == set(
        [
            '',
            '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.SoftDelete:soft_delete',
            '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.TestTriggerProxy:protect_delete',
        ]
    )

    call_command('pgtrigger', 'disable')
    call_command(
        'pgtrigger',
        'ls',
        'tests.SoftDelete:soft_delete',
        'tests.TestTriggerProxy:protect_delete',
    )

    lines = capsys.readouterr().out.split('\n')
    assert set(lines) == set(
        [
            '',
            '\x1b[92mINSTALLED\x1b[0m \x1b[91mDISABLED\x1b[0m tests.SoftDelete:soft_delete',
            '\x1b[92mINSTALLED\x1b[0m \x1b[91mDISABLED\x1b[0m tests.TestTriggerProxy:protect_delete',
        ]
    )

    call_command('pgtrigger', 'enable')
    call_command(
        'pgtrigger',
        'ls',
        'tests.SoftDelete:soft_delete',
        'tests.TestTriggerProxy:protect_delete',
    )

    lines = capsys.readouterr().out.split('\n')
    assert set(lines) == set(
        [
            '',
            '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.SoftDelete:soft_delete',
            '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.TestTriggerProxy:protect_delete',
        ]
    )


@pytest.mark.django_db
def test_prune(capsys):
    """Test pruning a trigger"""
    # Make it appear as though the trigger has been renamed and is no
    # longer installed
    soft_delete_model, soft_delete_trigger = pgtrigger.registered("tests.SoftDelete:soft_delete")[
        0
    ]
    with soft_delete_trigger.unregister(soft_delete_model):
        call_command('pgtrigger', 'ls')
        captured = capsys.readouterr()
        lines = sorted(captured.out.split('\n'))
        assert (
            '\x1b[96mPRUNE\x1b[0m     \x1b[92mENABLED\x1b[0m tests_softdelete:pgtrigger_soft_delete_f41be'
        ) in lines

        call_command('pgtrigger', 'prune')

    call_command('pgtrigger', 'ls')
    lines = capsys.readouterr().out.split('\n')
    assert (
        '\x1b[91mUNINSTALLED\x1b[0m \x1b[94mN/A\x1b[0m     tests.SoftDelete:soft_delete'
    ) in lines

    call_command('pgtrigger', 'install')
    call_command('pgtrigger', 'ls')
    lines = capsys.readouterr().out.split('\n')
    assert (
        '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.SoftDelete:soft_delete'
    ) in lines


@pytest.mark.django_db(databases=['default', 'other'])
def test_outdated(capsys, mocker):
    """Test an outdated trigger"""
    # Make it appear like the trigger is out of date by changing
    # its hash
    mocker.patch.object(
        registry._registry['tests.SoftDelete:soft_delete'][1],
        'get_hash',
        return_value='hash',
    )

    call_command('pgtrigger', 'ls')
    lines = capsys.readouterr().out.split('\n')
    assert (
        '\x1b[93mOUTDATED\x1b[0m  \x1b[92mENABLED\x1b[0m tests.SoftDelete:soft_delete'
    ) in lines


@pytest.mark.django_db
def test_main_commands_w_args(capsys):
    """
    Tests running main commands with arguments
    """

    call_command('pgtrigger', 'uninstall', 'tests.SoftDelete:soft_delete')
    call_command(
        'pgtrigger',
        'ls',
        'tests.SoftDelete:soft_delete',
        'tests.TestTriggerProxy:protect_delete',
    )

    lines = capsys.readouterr().out.split('\n')
    assert set(lines) == set(
        [
            '\x1b[91mUNINSTALLED\x1b[0m \x1b[94mN/A\x1b[0m     tests.SoftDelete:soft_delete',
            '\x1b[92mINSTALLED\x1b[0m   \x1b[92mENABLED\x1b[0m tests.TestTriggerProxy:protect_delete',
            '',
        ]
    )

    call_command('pgtrigger', 'install', 'tests.SoftDelete:soft_delete')
    call_command(
        'pgtrigger',
        'ls',
        'tests.SoftDelete:soft_delete',
        'tests.TestTriggerProxy:protect_delete',
    )

    lines = capsys.readouterr().out.split('\n')
    assert set(lines) == set(
        [
            '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.SoftDelete:soft_delete',
            '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.TestTriggerProxy:protect_delete',
            '',
        ]
    )

    call_command('pgtrigger', 'disable', 'tests.SoftDelete:soft_delete')
    call_command(
        'pgtrigger',
        'ls',
        'tests.SoftDelete:soft_delete',
        'tests.TestTriggerProxy:protect_delete',
    )

    lines = capsys.readouterr().out.split('\n')
    assert set(lines) == set(
        [
            '\x1b[92mINSTALLED\x1b[0m \x1b[91mDISABLED\x1b[0m tests.SoftDelete:soft_delete',
            '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m  tests.TestTriggerProxy:protect_delete',
            '',
        ]
    )

    call_command('pgtrigger', 'enable', 'tests.SoftDelete:soft_delete')
    call_command(
        'pgtrigger',
        'ls',
        'tests.SoftDelete:soft_delete',
        'tests.TestTriggerProxy:protect_delete',
    )

    lines = capsys.readouterr().out.split('\n')
    assert set(lines) == set(
        [
            '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.SoftDelete:soft_delete',
            '\x1b[92mINSTALLED\x1b[0m \x1b[92mENABLED\x1b[0m tests.TestTriggerProxy:protect_delete',
            '',
        ]
    )

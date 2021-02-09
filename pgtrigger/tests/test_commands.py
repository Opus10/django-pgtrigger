from unittest import mock

from django.core.management import call_command
import pytest

from pgtrigger import core


@pytest.mark.django_db
def test_full_ls(capsys):
    """Tests listing all triggers"""

    call_command('pgtrigger', 'ls')

    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
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
        '\tdefault'
        '\t\x1b[92mINSTALLED\x1b[0m'
        '\t\x1b[92mENABLED\x1b[0m',
        'tests.ToLogModel:after_update_statement_test'
        '\tdefault'
        '\t\x1b[92mINSTALLED\x1b[0m'
        '\t\x1b[92mENABLED\x1b[0m',
        'tests.ToLogModel:update_of_statement_test'
        '\tdefault'
        '\t\x1b[92mINSTALLED\x1b[0m'
        '\t\x1b[92mENABLED\x1b[0m',
    ]


@pytest.mark.django_db
def test_subset_ls(capsys):
    """Tests listing some triggers"""

    call_command(
        'pgtrigger',
        'ls',
        'tests.SoftDelete:soft_delete',
        'tests.TestTrigger:protect_delete',
    )

    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    assert lines == [
        '',
        'tests.SoftDelete:soft_delete'
        '\tdefault'
        '\t\x1b[92mINSTALLED\x1b[0m'
        '\t\x1b[92mENABLED\x1b[0m',
        'tests.TestTrigger:protect_delete'
        '\tdefault'
        '\t\x1b[92mINSTALLED\x1b[0m'
        '\t\x1b[92mENABLED\x1b[0m',
    ]


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
        'tests.TestTrigger:protect_delete',
    )

    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    assert lines == [
        '',
        'tests.SoftDelete:soft_delete\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
        'tests.TestTrigger:protect_delete'
        '\tdefault'
        '\t\x1b[91mUNINSTALLED\x1b[0m',
    ]

    call_command('pgtrigger', 'install')
    call_command(
        'pgtrigger',
        'ls',
        'tests.SoftDelete:soft_delete',
        'tests.TestTrigger:protect_delete',
    )

    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    assert lines == [
        '',
        'tests.SoftDelete:soft_delete'
        '\tdefault'
        '\t\x1b[92mINSTALLED\x1b[0m'
        '\t\x1b[92mENABLED\x1b[0m',
        'tests.TestTrigger:protect_delete'
        '\tdefault'
        '\t\x1b[92mINSTALLED\x1b[0m'
        '\t\x1b[92mENABLED\x1b[0m',
    ]

    call_command('pgtrigger', 'disable')
    call_command(
        'pgtrigger',
        'ls',
        'tests.SoftDelete:soft_delete',
        'tests.TestTrigger:protect_delete',
    )

    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    assert lines == [
        '',
        'tests.SoftDelete:soft_delete'
        '\tdefault'
        '\t\x1b[92mINSTALLED\x1b[0m'
        '\t\x1b[91mDISABLED\x1b[0m',
        'tests.TestTrigger:protect_delete'
        '\tdefault'
        '\t\x1b[92mINSTALLED\x1b[0m'
        '\t\x1b[91mDISABLED\x1b[0m',
    ]

    call_command('pgtrigger', 'enable')
    call_command(
        'pgtrigger',
        'ls',
        'tests.SoftDelete:soft_delete',
        'tests.TestTrigger:protect_delete',
    )

    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    assert lines == [
        '',
        'tests.SoftDelete:soft_delete'
        '\tdefault'
        '\t\x1b[92mINSTALLED\x1b[0m'
        '\t\x1b[92mENABLED\x1b[0m',
        'tests.TestTrigger:protect_delete'
        '\tdefault'
        '\t\x1b[92mINSTALLED\x1b[0m'
        '\t\x1b[92mENABLED\x1b[0m',
    ]


@pytest.mark.django_db
def test_prune(capsys):
    """Test pruning a trigger"""
    # Make it appear as though the trigger has been renamed and is no
    # longer installed
    with mock.patch.dict(core.registry, {}, clear=True):
        call_command('pgtrigger', 'ls')
        captured = capsys.readouterr()
        lines = sorted(captured.out.split('\n'))
        assert (
            'tests_softdelete:pgtrigger_soft_delete_f41be'
            '\tdefault'
            '\t\x1b[96mPRUNE\x1b[0m'
            '\t\x1b[92mENABLED\x1b[0m'
        ) in lines

        call_command('pgtrigger', 'prune')

    call_command('pgtrigger', 'ls')
    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    assert (
        'tests.SoftDelete:soft_delete'
        '\tdefault'
        '\t\x1b[91mUNINSTALLED\x1b[0m'
    ) in lines

    call_command('pgtrigger', 'install')
    call_command('pgtrigger', 'ls')
    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    assert (
        'tests.SoftDelete:soft_delete'
        '\tdefault'
        '\t\x1b[92mINSTALLED\x1b[0m'
        '\t\x1b[92mENABLED\x1b[0m'
    ) in lines


@pytest.mark.django_db
def test_outdated(capsys, mocker):
    """Test an outdated trigger"""
    # Make it appear like the trigger is out of date by changing
    # its hash
    mocker.patch.object(
        core.registry['tests.SoftDelete:soft_delete'][1],
        'get_hash',
        return_value='hash',
    )

    call_command(
        'pgtrigger', 'ls',
    )
    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    assert (
        'tests.SoftDelete:soft_delete'
        '\tdefault'
        '\t\x1b[93mOUTDATED\x1b[0m'
        '\t\x1b[92mENABLED\x1b[0m'
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
        'tests.TestTrigger:protect_delete',
    )

    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    assert lines == [
        '',
        'tests.SoftDelete:soft_delete\tdefault\t\x1b[91mUNINSTALLED\x1b[0m',
        'tests.TestTrigger:protect_delete'
        '\tdefault'
        '\t\x1b[92mINSTALLED\x1b[0m'
        '\t\x1b[92mENABLED\x1b[0m',
    ]

    call_command('pgtrigger', 'install', 'tests.SoftDelete:soft_delete')
    call_command(
        'pgtrigger',
        'ls',
        'tests.SoftDelete:soft_delete',
        'tests.TestTrigger:protect_delete',
    )

    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    assert lines == [
        '',
        'tests.SoftDelete:soft_delete'
        '\tdefault'
        '\t\x1b[92mINSTALLED\x1b[0m'
        '\t\x1b[92mENABLED\x1b[0m',
        'tests.TestTrigger:protect_delete'
        '\tdefault'
        '\t\x1b[92mINSTALLED\x1b[0m'
        '\t\x1b[92mENABLED\x1b[0m',
    ]

    call_command('pgtrigger', 'disable', 'tests.SoftDelete:soft_delete')
    call_command(
        'pgtrigger',
        'ls',
        'tests.SoftDelete:soft_delete',
        'tests.TestTrigger:protect_delete',
    )

    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    assert lines == [
        '',
        'tests.SoftDelete:soft_delete'
        '\tdefault'
        '\t\x1b[92mINSTALLED\x1b[0m'
        '\t\x1b[91mDISABLED\x1b[0m',
        'tests.TestTrigger:protect_delete'
        '\tdefault'
        '\t\x1b[92mINSTALLED\x1b[0m'
        '\t\x1b[92mENABLED\x1b[0m',
    ]

    call_command('pgtrigger', 'enable', 'tests.SoftDelete:soft_delete')
    call_command(
        'pgtrigger',
        'ls',
        'tests.SoftDelete:soft_delete',
        'tests.TestTrigger:protect_delete',
    )

    captured = capsys.readouterr()
    lines = sorted(captured.out.split('\n'))
    assert lines == [
        '',
        'tests.SoftDelete:soft_delete'
        '\tdefault'
        '\t\x1b[92mINSTALLED\x1b[0m'
        '\t\x1b[92mENABLED\x1b[0m',
        'tests.TestTrigger:protect_delete'
        '\tdefault'
        '\t\x1b[92mINSTALLED\x1b[0m'
        '\t\x1b[92mENABLED\x1b[0m',
    ]

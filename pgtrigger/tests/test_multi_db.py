"""Tests multi-database support"""

import contextlib

import ddf
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import transaction
from django.db.utils import InternalError
import pytest

import pgtrigger
from pgtrigger import core
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


@pytest.fixture(autouse=True)
def routed_db(settings):
    settings.DATABASE_ROUTERS = [
        'pgtrigger.tests.test_multi_db.ToLogRouter',
        'pgtrigger.tests.models.Router',
    ]


@pytest.mark.django_db(databases=["default", "sqlite", "other"], transaction=True)
def test_multi_db_ignore():
    """Tests ignoring triggers across multiple databases"""
    trigger = pgtrigger.Protect(operation=pgtrigger.Delete, name="protect_deletes")

    with contextlib.ExitStack() as stack:
        stack.enter_context(trigger.register(models.ToLogModel))
        stack.enter_context(trigger.register(User))
        stack.enter_context(trigger.install(models.ToLogModel, database="other"))
        stack.enter_context(trigger.install(User))

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
    lines = [line for line in captured.out.split('\n') if line]
    for line in lines:
        assert "\x1b[92mINSTALLED\x1b[0m" in line

    call_command('pgtrigger', 'ls', '-d', 'other')
    captured = capsys.readouterr()
    lines = [line for line in captured.out.split('\n') if line]
    for line in lines:
        # The router ignores partition models for the default DB
        if "tests.PartitionModel:protect_delete" in line:
            assert "\x1b[94mUNALLOWED\x1b[0m" in line
        else:
            assert "\x1b[92mINSTALLED\x1b[0m" in line

    call_command('pgtrigger', 'ls', '-d', 'sqlite')
    captured = capsys.readouterr()
    lines = [line for line in captured.out.split('\n') if line]
    for line in lines:
        assert "\x1b[94mUNALLOWED\x1b[0m" in line


@pytest.mark.django_db(databases=["other"])
def test_disable_enable(capsys):
    call_command('pgtrigger', 'disable', '-d', 'other')
    for model, trigger in pgtrigger.registered():
        expected_status = None if model == models.PartitionModel else False
        assert trigger.get_installation_status(model, database='other')[1] is expected_status

    call_command('pgtrigger', 'enable', '--database', 'other')
    for model, trigger in pgtrigger.registered():
        expected_status = None if model == models.PartitionModel else True
        assert trigger.get_installation_status(model, database='other')[1] is expected_status


@pytest.mark.django_db(databases=["sqlite"])
def test_ignore_non_postgres_dbs():
    call_command('pgtrigger', 'uninstall', '-d', 'sqlite')
    call_command('pgtrigger', 'install', '-d', 'sqlite')
    call_command('pgtrigger', 'install', '-d', 'sqlite')
    call_command('pgtrigger', 'prune', '-d', 'sqlite')


@pytest.mark.django_db(databases=["other", "default", "sqlite"])
def test_uninstall_install():
    for model, trigger in pgtrigger.registered():
        expected_status = core.UNALLOWED if model == models.PartitionModel else core.INSTALLED
        assert trigger.get_installation_status(model, database='other')[0] == expected_status

    call_command('pgtrigger', 'uninstall', '-d', 'other')
    call_command('pgtrigger', 'uninstall', '-d', 'default')
    for model, trigger in pgtrigger.registered():
        expected_status = core.UNALLOWED if model == models.PartitionModel else core.UNINSTALLED
        assert trigger.get_installation_status(model, database='other')[0] == expected_status

    call_command('pgtrigger', 'install', '--database', 'other')
    for model, trigger in pgtrigger.registered():
        expecetd_status = core.UNALLOWED if model == models.PartitionModel else core.INSTALLED
        assert trigger.get_installation_status(model, database='other')[0] == expecetd_status

    for model, trigger in pgtrigger.registered():
        assert trigger.get_installation_status(model, database='default')[0] == core.UNINSTALLED

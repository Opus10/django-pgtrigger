import pytest

import pgtrigger
from pgtrigger import registry
from pgtrigger.tests import models


def test_registered_invalid_args():
    with pytest.raises(ValueError):
        pgtrigger.registered('uri')


def test_registry():
    """
    Tests dynamically registering and unregistering triggers
    """
    init_registry_size = len(registry._registry)
    # The trigger registry should already be populated with our test triggers
    assert init_registry_size >= 6

    # Add a trigger to the registry
    trigger = pgtrigger.Trigger(
        when=pgtrigger.Before,
        name='my_aliased_trigger',
        operation=pgtrigger.Insert | pgtrigger.Update,
        func="RAISE EXCEPTION 'no no no!';",
    )

    # Register/unregister in context managers. The state should be the same
    # at the end as the beginning
    with trigger.register(models.TestModel):
        assert len(registry._registry) == init_registry_size + 1
        assert f'tests.TestModel:{trigger.name}' in registry._registry

        with trigger.unregister(models.TestModel):
            assert len(registry._registry) == init_registry_size
            assert f'tests.TestModel:{trigger.name}' not in registry._registry

        # Try obtaining trigger by alias
        assert pgtrigger.registered('tests.TestModel:my_aliased_trigger')

    assert len(registry._registry) == init_registry_size
    assert f'tests.TestModel:{trigger.name}' not in registry._registry
    with pytest.raises(KeyError, match='not found'):
        pgtrigger.registered(f'tests.TestModel:{trigger.name}')

    with pytest.raises(ValueError, match='must be in the format'):
        pgtrigger.registered('tests.TestMode')


def test_duplicate_trigger_names(mocker):
    """Ensure that duplicate trigger names are properly detected"""

    # Add a trigger to the registry
    trigger1 = pgtrigger.Trigger(
        name='mytrigger', when=pgtrigger.Before, operation=pgtrigger.Insert
    )
    trigger2 = pgtrigger.Protect(
        name='mytrigger', when=pgtrigger.Before, operation=pgtrigger.Insert
    )
    trigger3 = pgtrigger.Trigger(
        name='MyTrigger', when=pgtrigger.Before, operation=pgtrigger.Insert
    )

    assert trigger1.get_pgid(models.TestModel) == 'pgtrigger_mytrigger_b34c5'
    assert trigger3.get_pgid(models.TestModel) == 'pgtrigger_mytrigger_4a08f'

    # Check that a conflict cannot happen in the registry.
    # NOTE - use context managers to ensure we don't keep around
    # these registered triggers in other tests
    with trigger1.register(models.TestModel):
        with pytest.raises(KeyError, match='already used'):
            with trigger2.register(models.TestModel):
                pass

    mocker.patch.object(pgtrigger.Trigger, 'get_pgid', return_value='duplicate')

    # Check that a conflict cannot happen in the generated postgres ID.
    # NOTE - use context managers to ensure we don't keep around
    # these registered triggers in other tests
    with pytest.raises(KeyError, match="already in use"):
        with trigger1.register(models.TestModel):
            pass


def test_duplicate_trigger_names_proxy_model(mocker):
    """Test that duplicate trigger names are detected when using proxy models"""

    # TestTriggerProxy registers "protect_delete" for TestTrigger.
    # If we try to register this trigger directly on TestTrigger, it should result
    # in a duplicate error
    trigger = pgtrigger.Trigger(
        name='protect_delete', when=pgtrigger.Before, operation=pgtrigger.Insert
    )
    with pytest.raises(KeyError, match='already used'):
        with trigger.register(models.TestTrigger):
            pass

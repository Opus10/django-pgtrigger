import ddf
from django.db.utils import InternalError
import pytest

import pgtrigger
from pgtrigger.tests import models


def test_registered_invalid_args():
    with pytest.raises(ValueError):
        pgtrigger.registered('uri')


@pytest.mark.django_db
def test_search_model():
    """Verifies search model fields are kept up to date"""
    obj = models.SearchModel.objects.create(
        title="This is a message", body="Hello World. What a great body."
    )
    models.SearchModel.objects.create(title="Hi guys", body="Random Word. This is a good idea.")
    models.SearchModel.objects.create(
        title="Hello", body="Other words. Many great ideas come from stuff."
    )
    models.SearchModel.objects.create(title="The title", body="A short message.")

    assert models.SearchModel.objects.filter(body_vector="hello").count() == 1
    assert models.SearchModel.objects.filter(body_vector="words").count() == 2
    assert models.SearchModel.objects.filter(body_vector="world").count() == 1
    assert models.SearchModel.objects.filter(title_body_vector="message").count() == 2
    assert models.SearchModel.objects.filter(title_body_vector="idea").count() == 2
    assert models.SearchModel.objects.filter(title_body_vector="hello").count() == 2

    obj.body = "Nothing more"
    obj.save()
    assert not models.SearchModel.objects.filter(body_vector="hello").exists()
    assert models.SearchModel.objects.filter(title_body_vector="hello").count() == 1


def test_update_search_vector_args():
    """Verifies arg checking for UpdateSearchVector"""
    with pytest.raises(ValueError, match='provide "vector_field"'):
        pgtrigger.UpdateSearchVector()

    with pytest.raises(ValueError, match='provide "document_fields"'):
        pgtrigger.UpdateSearchVector(vector_field="vector_field")


def test_update_search_vector_ignore():
    """Verifies UpdateSearchVector cannot be ignored"""
    trigger = pgtrigger.UpdateSearchVector(
        name="hi", vector_field="vector_field", document_fields=["hi"]
    )
    with pytest.raises(RuntimeError, match="Cannot ignore UpdateSearchVector"):
        with trigger.ignore(models.SearchModel):
            pass


@pytest.mark.django_db
def test_soft_delete():
    """
    Verifies the SoftDelete test model has the "is_active" flag set to false
    """
    soft_delete = ddf.G(models.SoftDelete, is_active=True)
    ddf.G(models.FkToSoftDelete, ref=soft_delete)
    soft_delete.delete()

    assert not models.SoftDelete.objects.get().is_active
    assert not models.FkToSoftDelete.objects.exists()


@pytest.mark.django_db
def test_customer_soft_delete():
    """
    Verifies the CustomSoftDelete test model has the "custom_active" flag set
    to false
    """
    soft_delete = ddf.G(models.CustomSoftDelete, custom_active=True)
    soft_delete.delete()

    assert not models.CustomSoftDelete.objects.get().custom_active


@pytest.mark.django_db
def test_soft_delete_different_values():
    """
    Tests SoftDelete with different types of fields and values
    """
    # Make the LogEntry model a soft delete model where
    # "level" is set to "inactive"
    trigger = pgtrigger.SoftDelete(name='soft_delete', field='level', value='inactive')
    with trigger.install(models.LogEntry):
        le = ddf.G(models.LogEntry, level='active')
        le.delete()
        assert models.LogEntry.objects.get().level == 'inactive'
    models.LogEntry.objects.all().delete()

    # Make the LogEntry model a soft delete model where
    # "old_field" is set to None
    trigger = pgtrigger.SoftDelete(name='soft_delete', field='old_field', value=None)
    with trigger.install(models.LogEntry):
        le = ddf.G(models.LogEntry, old_field='something')
        le.delete()
        assert models.LogEntry.objects.get().old_field is None


@pytest.mark.django_db(transaction=True)
def test_fsm():
    """
    Verifies the FSM test model cannot make invalid transitions
    """
    fsm = ddf.G(models.FSM, transition='unpublished')
    fsm.transition = 'inactive'
    with pytest.raises(InternalError, match='Invalid transition'):
        fsm.save()

    fsm.transition = 'published'
    fsm.save()

    # Be sure we ignore FSM when there is no transition
    fsm.save()

    with pytest.raises(InternalError, match='Invalid transition'):
        fsm.transition = 'unpublished'
        fsm.save()

    fsm.transition = 'inactive'
    fsm.save()


@pytest.mark.django_db
def test_protect():
    """Verify deletion protect trigger works on test model"""
    deletion_protected_model = ddf.G(models.TestTrigger)
    with pytest.raises(InternalError, match='Cannot delete rows'):
        deletion_protected_model.delete()


@pytest.mark.django_db
def test_custom_db_table_protect_trigger():
    """Verify custom DB table names have successful triggers"""
    deletion_protected_model = ddf.G(models.CustomTableName)
    with pytest.raises(InternalError, match='Cannot delete rows'):
        deletion_protected_model.delete()

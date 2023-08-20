from django.db import connection
import pytest

from pgtrigger.tests import utils
import pgtrigger.tests.test_syncdb_app.models as syncdb_models


# Adapted from django's tests/schema/tests.py
def delete_tables(models):
    "Deletes all model tables for our models for a clean test environment"
    converter = connection.introspection.identifier_converter
    with connection.schema_editor() as editor:
        connection.disable_constraint_checking()
        table_names = connection.introspection.table_names()
        for model in models:
            tbl = converter(model._meta.db_table)
            if tbl in table_names:
                editor.delete_model(model)
                table_names.remove(tbl)
        connection.enable_constraint_checking()


@pytest.mark.django_db
def test_create_model_creates_triggers():
    """create_model is called when the django app doesn't have a migrations module.
    create_model is also called during a `CreateTable` migration operation
    but as the triggers aren't stored with the CreateTable operation, the
    specific code that creates triggers in `create_model` isn't executed.
    """
    delete_tables([syncdb_models.NoMigrationModel])
    try:
        with connection.schema_editor() as editor:
            editor.create_model(syncdb_models.NoMigrationModel)
        with utils.raises_trigger_error(match="no no no!"):
            syncdb_models.NoMigrationModel.objects.create(field="misc_insert", int_field=1)
    finally:
        delete_tables([syncdb_models.NoMigrationModel])

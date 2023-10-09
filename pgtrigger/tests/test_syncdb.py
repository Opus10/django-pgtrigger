import pytest
from django.db import connection

import pgtrigger.tests.syncdb_app.models as syncdb_models
from pgtrigger.tests import utils


@pytest.mark.django_db
def test_create_model_creates_triggers():
    """
    Tests trigger installation with syncdb

    `DatabaseSchemaEditorMixin.create_model` is called when the django app doesn't
    have a migrations module. `DatabaseSchemaEditorMixin.create_model` is also called
    during a `CreateTable` migration operation but as the triggers aren't stored with
    the `CreateTable operation`, the specific code that creates triggers in
    `DatabaseSchemaEditorMixin.create_model` isn't executed.
    """
    with connection.schema_editor() as editor:
        editor.create_model(syncdb_models.NoMigrationModel)

    with utils.raises_trigger_error(match="no no no!"):
        syncdb_models.NoMigrationModel.objects.create(field="misc_insert", int_field=1)

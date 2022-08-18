from django.contrib.auth.models import User
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.utils import timezone
from psqlextra.models import PostgresPartitionedModel
from psqlextra.types import PostgresPartitioningMethod

import pgtrigger


class Router:
    route_app_labels = ['tests']

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if model_name == 'partitionmodel' and db in ('sqlite', 'other'):
            return False


class PartitionModel(PostgresPartitionedModel):
    class PartitioningMeta:
        method = PostgresPartitioningMethod.RANGE
        key = ["timestamp"]

    name = models.TextField()
    timestamp = models.DateTimeField()

    class Meta:
        triggers = [pgtrigger.Protect(name="protect_delete", operation=pgtrigger.Delete)]


class OrderSchema(models.Model):
    """A model that only appears in the "schema1" schema"""

    int_field = models.IntegerField()


class ReceiptSchema(models.Model):
    """A model that only appears in the "schema2" schema"""

    char_field = models.CharField(max_length=128)

    class Meta:
        db_table = "table.with.dots"


class SearchModel(models.Model):
    body_vector = SearchVectorField()
    title_body_vector = SearchVectorField()

    title = models.CharField(max_length=128)
    body = models.TextField()

    class Meta:
        triggers = [
            pgtrigger.UpdateSearchVector(
                name="add_body_to_vector", vector_field="body_vector", document_fields=["body"]
            ),
            pgtrigger.UpdateSearchVector(
                name="add_body_title_to_vector",
                vector_field="title_body_vector",
                document_fields=["body", "title"],
            ),
        ]


@pgtrigger.register(
    pgtrigger.Protect(name='protect_delete', operation=pgtrigger.Delete),
)
class CustomTableName(models.Model):
    int_field = models.IntegerField(null=True, unique=True)

    class Meta:
        db_table = "order"


class TestModel(models.Model):
    int_field = models.IntegerField(null=True, unique=True)
    char_field = models.CharField(max_length=128, null=True)
    float_field = models.FloatField(null=True)

    class Meta:
        unique_together = ('int_field', 'char_field')


class LogEntry(models.Model):
    """Created when ToLogModel is updated"""

    level = models.CharField(max_length=16)
    old_field = models.CharField(max_length=16, null=True)
    new_field = models.CharField(max_length=16, null=True)


@pgtrigger.register(
    pgtrigger.Trigger(
        name='update_of_statement_test',
        level=pgtrigger.Statement,
        operation=pgtrigger.UpdateOf('field'),
        when=pgtrigger.After,
        func=f'''
            INSERT INTO {LogEntry._meta.db_table}(level)
            VALUES ('STATEMENT');
            RETURN NULL;
        ''',
    ),
    pgtrigger.Trigger(
        name='after_update_statement_test',
        level=pgtrigger.Statement,
        operation=pgtrigger.Update,
        when=pgtrigger.After,
        referencing=pgtrigger.Referencing(old='old_values', new='new_values'),
        func=f'''
            INSERT INTO {LogEntry._meta.db_table}(level, old_field, new_field)
            SELECT 'STATEMENT' AS level,
                   old_values.field AS old_field,
                   new_values.field AS new_field
                 FROM old_values
                 JOIN new_values ON old_values.id = new_values.id;
            RETURN NULL;
        ''',
    ),
    pgtrigger.Trigger(
        name='after_update_row_test',
        level=pgtrigger.Row,
        operation=pgtrigger.Update,
        when=pgtrigger.After,
        condition=pgtrigger.Q(old__field__df=pgtrigger.F("new__field")),
        func=(f'INSERT INTO {LogEntry._meta.db_table}(level) VALUES (\'ROW\'); RETURN NULL;'),
    ),
)
class ToLogModel(models.Model):
    """For testing triggers that log records at statement and row level"""

    field = models.CharField(max_length=16)


class CharPk(models.Model):
    custom_pk = models.CharField(primary_key=True, max_length=32)


class TestTrigger(models.Model):
    """
    For testing triggers
    """

    field = models.CharField(max_length=16)
    int_field = models.IntegerField(default=0)
    dt_field = models.DateTimeField(default=timezone.now)
    nullable = models.CharField(null=True, default=None, max_length=16)
    fk_field = models.ForeignKey('auth.User', null=True, on_delete=models.CASCADE)
    char_pk_fk_field = models.ForeignKey(CharPk, null=True, on_delete=models.CASCADE)
    m2m_field = models.ManyToManyField(User, related_name="+")

    class Meta:
        triggers = [
            pgtrigger.Trigger(
                name='protect_misc_insert',
                when=pgtrigger.Before,
                operation=pgtrigger.Insert,
                func="RAISE EXCEPTION 'no no no!';",
                condition=pgtrigger.Q(new__field='misc_insert'),
            ),
        ]


class TestTriggerProxy(TestTrigger):
    """
    For testing triggers on proxy models
    """

    class Meta:
        proxy = True
        triggers = [
            pgtrigger.Protect(name='protect_delete', operation=pgtrigger.Delete),
        ]


class TestDefaultThrough(TestTrigger.m2m_field.through):
    class Meta:
        proxy = True
        triggers = [
            pgtrigger.Protect(name='protect_it', operation=pgtrigger.Delete),
        ]


@pgtrigger.register(pgtrigger.SoftDelete(name='soft_delete', field='is_active'))
class SoftDelete(models.Model):
    """
    For testing soft deletion. Deletions on this model will set
    is_active = False without deleting the model
    """

    is_active = models.BooleanField(default=True)
    other_field = models.TextField()


class FkToSoftDelete(models.Model):
    """Ensures foreign keys to a soft delete model are deleted"""

    ref = models.ForeignKey(SoftDelete, on_delete=models.CASCADE)


@pgtrigger.register(pgtrigger.SoftDelete(name='soft_delete', field='custom_active'))
class CustomSoftDelete(models.Model):
    """
    For testing soft deletion with a custom active field.

    This trigger also helps ensure that triggers can have the same names
    across multiple models.
    """

    custom_active = models.BooleanField(default=True)
    other_field = models.TextField()


@pgtrigger.register(
    pgtrigger.FSM(
        name='fsm',
        field='transition',
        transitions=[('unpublished', 'published'), ('published', 'inactive')],
    )
)
class FSM(models.Model):
    """Tests valid transitions of a field"""

    transition = models.CharField(max_length=32)

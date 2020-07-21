from django.db import models
from django.utils import timezone

import pgtrigger


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
        level=pgtrigger.Statement,
        operation=pgtrigger.Update,
        when=pgtrigger.After,
        func=f'''
            INSERT INTO {LogEntry._meta.db_table}(level)
            VALUES ('STATEMENT');
            RETURN NULL;
        ''',
    ),
    pgtrigger.Trigger(
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
        level=pgtrigger.Row,
        operation=pgtrigger.Update,
        when=pgtrigger.After,
        func=(
            f'INSERT INTO {LogEntry._meta.db_table}(level) VALUES (\'ROW\');'
            ' RETURN NULL;'
        ),
    ),
)
class ToLogModel(models.Model):
    """For testing triggers that log records at statement and row level"""

    field = models.CharField(max_length=16)


class CharPk(models.Model):
    custom_pk = models.CharField(primary_key=True, max_length=32)


@pgtrigger.register(pgtrigger.Protect(operation=pgtrigger.Delete))
class TestTrigger(models.Model):
    """
    For testing triggers
    """

    field = models.CharField(max_length=16)
    int_field = models.IntegerField(default=0)
    dt_field = models.DateTimeField(default=timezone.now)
    nullable = models.CharField(null=True, default=None, max_length=16)
    fk_field = models.ForeignKey(
        'auth.User', null=True, on_delete=models.CASCADE
    )
    char_pk_fk_field = models.ForeignKey(
        CharPk, null=True, on_delete=models.CASCADE
    )


@pgtrigger.register(pgtrigger.SoftDelete(field='is_active'))
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

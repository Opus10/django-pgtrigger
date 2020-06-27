from django.db import models
from django.utils import timezone

import pgtrigger


class TestModel(models.Model):
    int_field = models.IntegerField(null=True, unique=True)
    char_field = models.CharField(max_length=128, null=True)
    float_field = models.FloatField(null=True)

    class Meta:
        unique_together = ('int_field', 'char_field')


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

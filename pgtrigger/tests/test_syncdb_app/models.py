from django.apps.registry import Apps
from django.db import models
from django.utils import timezone

import pgtrigger


syncdb_apps = Apps()


class NoMigrationModel(models.Model):
    """
    For testing triggers
    """

    field = models.CharField(max_length=16)
    int_field = models.IntegerField(default=0)
    dt_field = models.DateTimeField(default=timezone.now)
    nullable = models.CharField(null=True, default=None, max_length=16)

    class Meta:
        apps = syncdb_apps
        triggers = [
            pgtrigger.Trigger(
                name="protect_misc_insert",
                when=pgtrigger.Before,
                operation=pgtrigger.Insert,
                func="RAISE EXCEPTION 'no no no!';",
                condition=pgtrigger.Q(new__field="misc_insert"),
            ),
        ]

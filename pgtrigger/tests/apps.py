import django.apps
from django.db import connections
from django.db.models.signals import pre_migrate


def install_schemas(using, **kwargs):
    if connections[using].vendor == 'postgresql':
        with connections[using].cursor() as cursor:
            cursor.execute('CREATE SCHEMA IF NOT EXISTS "order";')
            cursor.execute('CREATE SCHEMA IF NOT EXISTS receipt;')


class PGTriggerTestsConfig(django.apps.AppConfig):
    name = 'pgtrigger.tests'

    def ready(self):
        """
        Ensure schemas are created for test databases before migrations
        """
        pre_migrate.connect(install_schemas, sender=self)

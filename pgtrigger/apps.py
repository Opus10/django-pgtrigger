import django.apps
from django.conf import settings
from django.db.models.signals import post_migrate


def install(using, **kwargs):
    import pgtrigger

    pgtrigger.install(database=using)


class PGTriggerConfig(django.apps.AppConfig):
    name = 'pgtrigger'

    def ready(self):
        """
        Install pgplus triggers in a post_migrate hook if any are
        configured.
        """
        if getattr(settings, 'PGTRIGGER_INSTALL_ON_MIGRATE', True):  # pragma: no branch
            post_migrate.connect(install, sender=self)

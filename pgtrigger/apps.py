import django.apps
from django.conf import settings
from django.db.models.signals import post_migrate


def install(**kwargs):
    import pgtrigger

    pgtrigger.install()


class PGTriggerConfig(django.apps.AppConfig):
    name = 'pgtrigger'

    def ready(self):
        """
        Install pgplus triggers in a post_migrate hook if any are
        configured.
        """
        if getattr(  # pragma: no branch
            settings, 'PGTRIGGER_INSTALL_ON_MIGRATE', True
        ):
            post_migrate.connect(install, sender=self)

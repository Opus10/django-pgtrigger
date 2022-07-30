import django.apps
from django.conf import settings
from django.db.models import options
from django.db.models.signals import post_migrate


# Allow triggers to be specified in model Meta options
if 'triggers' not in options.DEFAULT_NAMES:  # pragma: no branch
    options.DEFAULT_NAMES = options.DEFAULT_NAMES + ('triggers',)


def install(using, **kwargs):
    import pgtrigger

    pgtrigger.install(database=using)


class PGTriggerConfig(django.apps.AppConfig):
    name = 'pgtrigger'

    def ready(self):
        """
        Register all triggers in model Meta and
        install them in a post_migrate hook if any are
        configured.
        """
        import pgtrigger

        for model in django.apps.apps.get_models():
            for trigger in getattr(model._meta, "triggers", []):
                if not isinstance(trigger, pgtrigger.Trigger):  # pragma: no cover
                    raise TypeError(f"Triggers in {model} Meta must be pgtrigger.Trigger classes")

                trigger.register(model)

        if getattr(settings, 'PGTRIGGER_INSTALL_ON_MIGRATE', True):  # pragma: no branch
            post_migrate.connect(install, sender=self)

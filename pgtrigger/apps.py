import django.apps
from django.core.management.commands import makemigrations, migrate
from django.db.migrations import state
from django.db.models import options
from django.db.models.signals import post_migrate

import pgtrigger
import pgtrigger.features
import pgtrigger.migrations


# Allow triggers to be specified in model Meta. Users can turn this
# off via settings if it causes issues. If turned off, migrations
# are also disabled
if pgtrigger.features.model_meta():  # pragma: no branch
    if "triggers" not in options.DEFAULT_NAMES:  # pragma: no branch
        options.DEFAULT_NAMES = tuple(options.DEFAULT_NAMES) + ('triggers',)


# Patch the autodetector and model state detection if migrations are turned on
if pgtrigger.features.migrations():
    if 'triggers' not in state.DEFAULT_NAMES:  # pragma: no branch
        state.DEFAULT_NAMES = tuple(state.DEFAULT_NAMES) + ('triggers',)

    makemigrations.MigrationAutodetector = pgtrigger.migrations.MigrationAutodetector
    migrate.MigrationAutodetector = pgtrigger.migrations.MigrationAutodetector


def install_on_migrate(using, **kwargs):  # pragma: no cover
    pgtrigger.install(database=using)


class PGTriggerConfig(django.apps.AppConfig):
    name = 'pgtrigger'

    def ready(self):
        """
        Register all triggers in model Meta and
        install them in a post_migrate hook if any are
        configured.
        """

        # Populate the trigger registry from any ``Meta.triggers``
        if pgtrigger.features.model_meta():  # pragma: no branch
            for model in django.apps.apps.get_models():
                triggers = getattr(model._meta, "triggers", [])
                for trigger in triggers:
                    if not isinstance(trigger, pgtrigger.Trigger):  # pragma: no cover
                        raise TypeError(
                            f"Triggers in {model} Meta must be pgtrigger.Trigger classes"
                        )

                    trigger.register(model)

        # Configure triggers to automatically be installed after migrations
        if pgtrigger.features.install_on_migrate():  # pragma: no cover
            post_migrate.connect(install_on_migrate, sender=self)

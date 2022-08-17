import django.apps
from django.core.management.commands import makemigrations, migrate
import django.db.backends.postgresql.schema as postgresql_schema
from django.db.migrations import state
from django.db.models import options
from django.db.models.signals import post_migrate

from pgtrigger import core
from pgtrigger import features
from pgtrigger import installation
from pgtrigger import migrations


# Allow triggers to be specified in model Meta. Users can turn this
# off via settings if it causes issues. If turned off, migrations
# are also disabled
if features.model_meta():  # pragma: no branch
    if "triggers" not in options.DEFAULT_NAMES:  # pragma: no branch
        options.DEFAULT_NAMES = tuple(options.DEFAULT_NAMES) + ('triggers',)


# Patch the autodetector and model state detection if migrations are turned on
if features.migrations():  # pragma: no branch
    if 'triggers' not in state.DEFAULT_NAMES:  # pragma: no branch
        state.DEFAULT_NAMES = tuple(state.DEFAULT_NAMES) + ('triggers',)

    makemigrations.MigrationAutodetector = migrations.MigrationAutodetector
    migrate.MigrationAutodetector = migrations.MigrationAutodetector


if features.schema_editor():  # pragma: no branch
    postgresql_schema.DatabaseSchemaEditor = migrations.DatabaseSchemaEditor


def install_on_migrate(using, **kwargs):
    if features.install_on_migrate():
        installation.install(database=using)


class PGTriggerConfig(django.apps.AppConfig):
    name = 'pgtrigger'

    def ready(self):
        """
        Register all triggers in model Meta and
        install them in a post_migrate hook if any are
        configured.
        """

        # Populate the trigger registry from any ``Meta.triggers``
        if features.model_meta():  # pragma: no branch
            for model in django.apps.apps.get_models():
                triggers = getattr(model._meta, "triggers", [])
                for trigger in triggers:
                    if not isinstance(trigger, core.Trigger):  # pragma: no cover
                        raise TypeError(
                            f"Triggers in {model} Meta must be pgtrigger.Trigger classes"
                        )

                    trigger.register(model)

        # Configure triggers to automatically be installed after migrations
        post_migrate.connect(install_on_migrate, sender=self)

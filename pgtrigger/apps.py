import re

import django.apps
from django.conf import settings
from django.core import checks
from django.db.models import options
from django.db.models.signals import post_migrate

import pgtrigger


# Allow triggers to be specified in model Meta. Users can turn this
# off via settings if it causes issues
if (  # pragma: no branch
    getattr(settings, 'PGTRIGGER_MODEL_META', True) and 'triggers' not in options.DEFAULT_NAMES
):
    options.DEFAULT_NAMES = options.DEFAULT_NAMES + ('triggers',)


def register_trigger_meta():
    """
    Populate the trigger registry from any ``Meta.triggers``
    declarations.
    """
    if getattr(settings, 'PGTRIGGER_MODEL_META', True):  # pragma: no branch
        for model in django.apps.apps.get_models():
            triggers = getattr(model._meta, "triggers", [])
            for trigger in triggers:
                if not isinstance(trigger, pgtrigger.Trigger):  # pragma: no cover
                    raise TypeError(f"Triggers in {model} Meta must be pgtrigger.Trigger classes")

                trigger.register(model)

            # Delete the original option so that it doesn't appear in serializations
            model._meta.original_attrs.pop("triggers", None)


def patch_migration_checks():
    """
    When triggers are integrated with migrations, invalid checks occur. For example,
    trigger names can collide globally ("models.E032"), so we patch this check.
    User have the ability to turn off this patching and ignore model.E032 in settings
    if this patch causes any issues for their application.
    """
    if getattr(settings, 'PGTRIGGER_MIGRATIONS', True) and getattr(  # pragma: no branch
        settings, 'PGTRIGGER_PATCH_CHECKS', True
    ):
        orig_run_checks = checks.run_checks

        def run_checks(*args, **kwargs):
            """
            Ignore the "models.E032" check for any triggers.
            """
            all_trigger_names = {trigger.name for _, trigger in pgtrigger.get()}

            errors = orig_run_checks(*args, **kwargs)

            filtered_errors = []
            for error in errors:
                if error.id == "models.E032":
                    matches = re.findall(r'\'(.+)\'', error.msg)
                    if matches and matches[0] in all_trigger_names:
                        continue

                filtered_errors.append(error)  # pragma: no cover

            return filtered_errors

        checks.run_checks = run_checks


def install_on_migrate(using, **kwargs):  # pragma: no cover
    pgtrigger.install(database=using)


def configure_install_on_migrate(sender):
    """
    Configure triggers to automatically be installed after migrations
    if ``settings.PGTRIGGER_INSTALL_ON_MIGRATE`` is ``True``
    """
    if getattr(settings, 'PGTRIGGER_INSTALL_ON_MIGRATE', False):  # pragma: no cover
        post_migrate.connect(install_on_migrate, sender=sender)


class PGTriggerConfig(django.apps.AppConfig):
    name = 'pgtrigger'

    def ready(self):
        """
        Register all triggers in model Meta and
        install them in a post_migrate hook if any are
        configured.
        """
        register_trigger_meta()
        patch_migration_checks()
        configure_install_on_migrate(self)

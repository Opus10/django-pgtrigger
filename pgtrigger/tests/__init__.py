import django

if django.VERSION < (3, 2):  # pragma: no cover
    default_app_config = "pgtrigger.tests.apps.PGTriggerTestsConfig"

del django

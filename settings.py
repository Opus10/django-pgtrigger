import copy
import os

import django
import dj_database_url


SECRET_KEY = "django-pgtrigger"
# Install the tests as an app so that we can make test models
INSTALLED_APPS = [
    "pgtrigger",
    # For testing purposes
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.postgres",
    "psqlextra",
]

# Conditionally add the test app when we aren't building docs,
# otherwise sphinx builds won't work
if not os.environ.get("SPHINX"):
    INSTALLED_APPS += ["pgtrigger.tests"]

# Database url comes from the DATABASE_URL env var
# We have some multi-database and multi-schema tests
DATABASES = {
    "default": dj_database_url.config(),
    "sqlite": {"ENGINE": "django.db.backends.sqlite3", "NAME": "test_sqlite"},
}

DATABASES["other"] = copy.deepcopy(DATABASES["default"])
DATABASES["other"]["NAME"] += "_other"

DATABASES["default"]["ENGINE"] = "psqlextra.backend"

DATABASES["order"] = copy.deepcopy(DATABASES["default"])
DATABASES["order"]["OPTIONS"] = {"options": "-c search_path=order"}
DATABASES["receipt"] = copy.deepcopy(DATABASES["default"])
DATABASES["receipt"]["OPTIONS"] = {"options": "-c search_path=receipt"}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Ensure partitioned models dont get migrated for non-default DBs
DATABASE_ROUTERS = ["pgtrigger.tests.models.Router"]

# Turn off pgtrigger migrations for normal manage.py use
PGTRIGGER_MIGRATIONS = False

# Ensure that we always install triggers if running locally
PGTRIGGER_INSTALL_ON_MIGRATE = True

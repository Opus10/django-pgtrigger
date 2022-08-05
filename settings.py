import copy

import dj_database_url


SECRET_KEY = 'django-pgtrigger'
# Install the tests as an app so that we can make test models
INSTALLED_APPS = [
    'pgtrigger',
    'pgtrigger.tests',
    # For testing purposes
    'django.contrib.auth',
    'django.contrib.contenttypes',
]
# Database url comes from the DATABASE_URL env var
# We have some multi-database tests, so set up two databases
DATABASES = {
    'default': dj_database_url.config(),
    'sqlite': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': 'test_sqlite'},
}
DATABASES['other'] = copy.deepcopy(DATABASES['default'])
if 'NAME' in DATABASES['other']:
    DATABASES['other']['NAME'] += '_other'

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Turn off pgtrigger migrations for normal manage.py use
PGTRIGGER_MIGRATIONS = False

# Ensure that we always install triggers if running locally
PGTRIGGER_INSTALL_ON_MIGRATE = True

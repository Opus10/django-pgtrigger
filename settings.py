import copy

import dj_database_url
import pgconnection


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
}
DATABASES['other'] = copy.deepcopy(DATABASES['default'])
if 'NAME' in DATABASES['other']:
    DATABASES['other']['NAME'] += '_other'

DATABASES = pgconnection.configure(DATABASES)

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

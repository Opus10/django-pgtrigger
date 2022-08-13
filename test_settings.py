from settings import *

# Turn on pgtrigger migrations in the test suite
PGTRIGGER_MIGRATIONS = True

# We turn this on in tests to ensure that triggers are installed
# when the test database is set up. We dynamically turn it off
# when testing migrations.
PGTRIGGER_INSTALL_ON_MIGRATE = True

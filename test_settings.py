from settings import *

# Turn on pgtrigger migrations in the test suite
PGTRIGGER_MIGRATIONS = True

# Turn this off by default so that we can test migrations.
# The test suite automatically sets up fixtures at the
# beginning
PGTRIGGER_INSTALL_ON_MIGRATE = False

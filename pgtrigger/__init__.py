import django

from pgtrigger.core import After
from pgtrigger.core import Before
from pgtrigger.core import Condition
from pgtrigger.core import Delete
from pgtrigger.core import disable
from pgtrigger.core import enable
from pgtrigger.core import F
from pgtrigger.core import FSM
from pgtrigger.core import get
from pgtrigger.core import ignore
from pgtrigger.core import Insert
from pgtrigger.core import install
from pgtrigger.core import InsteadOf
from pgtrigger.core import IsDistinctFrom
from pgtrigger.core import IsNotDistinctFrom
from pgtrigger.core import Level
from pgtrigger.core import Operation
from pgtrigger.core import Operations
from pgtrigger.core import Protect
from pgtrigger.core import prune
from pgtrigger.core import Q
from pgtrigger.core import Referencing
from pgtrigger.core import register
from pgtrigger.core import Row
from pgtrigger.core import SoftDelete
from pgtrigger.core import Statement
from pgtrigger.core import Trigger
from pgtrigger.core import Truncate
from pgtrigger.core import uninstall
from pgtrigger.core import Update
from pgtrigger.core import UpdateOf
from pgtrigger.core import When
from pgtrigger.version import __version__

if django.VERSION < (3, 2):
    default_app_config = 'pgtrigger.apps.PGTriggerConfig'

del django


__all__ = [
    'After',
    'Before',
    'Condition',
    'Delete',
    'disable',
    'enable',
    'F',
    'FSM',
    'get',
    'ignore',
    'Insert',
    'install',
    'InsteadOf',
    'IsDistinctFrom',
    'IsNotDistinctFrom',
    'Level',
    'Operation',
    'Operations',
    'Protect',
    'prune',
    'Q',
    'Referencing',
    'register',
    'Row',
    'SoftDelete',
    'Statement',
    'Trigger',
    'Truncate',
    'uninstall',
    'Update',
    'UpdateOf',
    'When',
    '__version__',
]

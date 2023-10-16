import django

from pgtrigger.contrib import (
    FSM,
    Protect,
    ReadOnly,
    SoftDelete,
    UpdateSearchVector,
)
from pgtrigger.core import (
    After,
    AllChange,
    AllDontChange,
    AnyChange,
    AnyDontChange,
    Before,
    Condition,
    Deferred,
    Delete,
    F,
    Func,
    Immediate,
    Insert,
    InsteadOf,
    IsDistinctFrom,
    IsNotDistinctFrom,
    Level,
    Operation,
    Operations,
    Q,
    Referencing,
    Row,
    Statement,
    Timing,
    Trigger,
    Truncate,
    Update,
    UpdateOf,
    When,
)
from pgtrigger.installation import (
    disable,
    enable,
    install,
    prunable,
    prune,
    uninstall,
)
from pgtrigger.registry import (
    register,
    registered,
)
from pgtrigger.runtime import (
    constraints,
    ignore,
    schema,
)
from pgtrigger.version import __version__

if django.VERSION < (3, 2):  # pragma: no cover
    default_app_config = "pgtrigger.apps.PGTriggerConfig"

del django


__all__ = [
    "After",
    "AllChange",
    "AllDontChange",
    "AnyChange",
    "AnyDontChange",
    "Before",
    "Condition",
    "constraints",
    "Deferred",
    "Delete",
    "disable",
    "enable",
    "F",
    "FSM",
    "Func",
    "ignore",
    "Immediate",
    "Insert",
    "install",
    "InsteadOf",
    "IsDistinctFrom",
    "IsNotDistinctFrom",
    "Level",
    "Operation",
    "Operations",
    "Protect",
    "prunable",
    "prune",
    "Q",
    "ReadOnly",
    "Referencing",
    "register",
    "registered",
    "Row",
    "schema",
    "SoftDelete",
    "Statement",
    "Timing",
    "Trigger",
    "Truncate",
    "uninstall",
    "Update",
    "UpdateOf",
    "UpdateSearchVector",
    "When",
    "__version__",
]

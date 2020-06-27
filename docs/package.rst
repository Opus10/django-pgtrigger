Package
=======

When clause
-----------
.. autodata:: pgtrigger.After
.. autodata:: pgtrigger.Before

Operation clause
----------------
.. autodata:: pgtrigger.Truncate
.. autodata:: pgtrigger.Delete
.. autodata:: pgtrigger.Insert
.. autoclass:: pgtrigger.Update
.. autoclass:: pgtrigger.UpdateOf

Conditions
----------
.. autoclass:: pgtrigger.Condition
.. autoclass:: pgtrigger.Q
.. autoclass:: pgtrigger.F
.. autoclass:: pgtrigger.IsDistinctFrom
.. autoclass:: pgtrigger.IsNotDistinctFrom

Triggers
--------
.. autofunction:: pgtrigger.register
.. autoclass:: pgtrigger.Trigger
.. autoclass:: pgtrigger.Protect
.. autoclass:: pgtrigger.SoftDelete

Management
----------
.. autofunction:: pgtrigger.get
.. autofunction:: pgtrigger.install
.. autofunction:: pgtrigger.uninstall
.. autofunction:: pgtrigger.enable
.. autofunction:: pgtrigger.disable
.. autofunction:: pgtrigger.prune

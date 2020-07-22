Package
=======

Level clause
------------

.. autodata:: pgtrigger.Row
.. autodata:: pgtrigger.Statement

When clause
-----------
.. autodata:: pgtrigger.After
.. autodata:: pgtrigger.Before
.. autodata:: pgtrigger.InsteadOf

Operation clause
----------------
.. autodata:: pgtrigger.Truncate
.. autodata:: pgtrigger.Delete
.. autodata:: pgtrigger.Insert
.. autoclass:: pgtrigger.Update
.. autoclass:: pgtrigger.UpdateOf

Referencing clause
------------------

.. autoclass:: pgtrigger.Referencing

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
.. autoclass:: pgtrigger.FSM

Management
----------
.. autofunction:: pgtrigger.get
.. autofunction:: pgtrigger.install
.. autofunction:: pgtrigger.uninstall
.. autofunction:: pgtrigger.enable
.. autofunction:: pgtrigger.disable
.. autofunction:: pgtrigger.prune
.. autofunction:: pgtrigger.ignore

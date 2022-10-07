.. _module:

Module
~~~~~~

Below are the core classes and functions of the ``pgtrigger`` module.

Level clause
------------

.. autodata:: pgtrigger.Row

  For specifying row-level triggers (the default)

.. autodata:: pgtrigger.Statement

  For specifying statement-level triggers

When clause
-----------
.. autodata:: pgtrigger.After

  For specifying ``AFTER`` in the when clause of a trigger

.. autodata:: pgtrigger.Before

  For specifying ``BEFORE`` in the when clause of a trigger

.. autodata:: pgtrigger.InsteadOf

  For specifying ``INSTEAD OF`` in the when clause of a trigger

Operation clause
----------------
.. autodata:: pgtrigger.Truncate
  
  For specifying ``TRUNCATE`` as the trigger operation

.. autodata:: pgtrigger.Delete

  For specifying ``DELETE`` as the trigger operation

.. autodata:: pgtrigger.Insert

  For specifying ``INSERT`` as the trigger operation

.. autodata:: pgtrigger.Update

  For specifying ``UPDATE`` as the trigger operation

.. autoclass:: pgtrigger.UpdateOf

Referencing clause
------------------

.. autoclass:: pgtrigger.Referencing

Timing clause
-------------

.. autodata:: pgtrigger.Immediate
  
  For specifying ``IMMEDIATE`` as the default timing for deferrable triggers

.. autodata:: pgtrigger.Deferred

  For specifying ``DEFERRED`` as the default timing for deferrable triggers


Func clause
-----------

.. autoclass:: pgtrigger.Func

Conditions
----------
.. autoclass:: pgtrigger.Condition
.. autoclass:: pgtrigger.Q
.. autoclass:: pgtrigger.F
.. autoclass:: pgtrigger.IsDistinctFrom
.. autoclass:: pgtrigger.IsNotDistinctFrom

Triggers
--------
.. autoclass:: pgtrigger.Trigger
.. autoclass:: pgtrigger.Protect
.. autoclass:: pgtrigger.ReadOnly
.. autoclass:: pgtrigger.SoftDelete
.. autoclass:: pgtrigger.FSM
.. autoclass:: pgtrigger.UpdateSearchVector

Runtime execution
-----------------
.. autofunction:: pgtrigger.constraints
.. autofunction:: pgtrigger.ignore
.. autofunction:: pgtrigger.schema

Registry
--------
.. autofunction:: pgtrigger.register
.. autofunction:: pgtrigger.registered

Installation
------------
.. autofunction:: pgtrigger.install
.. autofunction:: pgtrigger.uninstall
.. autofunction:: pgtrigger.enable
.. autofunction:: pgtrigger.disable
.. autofunction:: pgtrigger.prunable
.. autofunction:: pgtrigger.prune

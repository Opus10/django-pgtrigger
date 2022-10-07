.. _cookbook:

Trigger Cookbook
================

Here we provide examples using the built-in triggers of
``django-pgtrigger`` and triggers that require raw SQL. While most
examples are practical application examples, some exist to illustrate
a starting point of how one can use triggers for more complex cases.

Read-only models and fields
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Ensure a set of fields on a model are read-only with
`pgtrigger.ReadOnly`. This trigger takes one of the following
optional arguments:

* **fields**: A list of read-only fields.
* **exclude**: Fields to exclude. All other fields will be
  read-only.

If no arguments are provided, the entire model will be read-only.

For example, here we have a model with a read-only ``created_at``
timestamp. Any changes to this field will result in an exception:

.. code-block:: python

    class TimestampedModel(models.Model):
        """Ensure created_at timestamp is read only"""
        created_at = models.DateTimeField(auto_now_add=True)
        editable_value = models.TextField()

        class Meta:
            triggers = [
                pgtrigger.ReadOnly(
                    name="read_only_created_at",
                    fields=["created_at"]
                )
            ]

.. note::

    A condition is automatically generated and cannot be supplied
    to `pgtrigger.ReadOnly`.

Validating field transitions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Similar to how one can configure a finite state machine on
a model field with `django-fsm <https://github.com/viewflow/django-fsm>`__,
the `pgtrigger.FSM` trigger ensures that a field can only do configured
transitions.

The example below ensures that the ``status`` field of a model
can only transition from "unpublished" to "published" and from
"published" to "inactive". Any other updates on the ``status`` field
will result in an exception:

.. code-block:: python

    class MyModel(models.Model):
        """Enforce valid transitions of the "status" field"""
        status = models.CharField(max_length=32, default="unpublished")

        class Meta:
            triggers = [
                pgtrigger.FSM(
                    name="status_fsm",
                    field="status",
                    transitions=[
                        ("unpublished", "published"),
                        ("published", "inactive"),
                    ]
                )
            ]

.. note::

    `pgtrigger.FSM` can be supplied with
    a ``condition`` to only enforce the state transitions when a condition
    is met.

.. note::

    The `pgtrigger.FSM` trigger only works for non-null
    ``CharField`` fields.

Mirroring a field
~~~~~~~~~~~~~~~~~

Here we create a `pgtrigger.Trigger` that runs before an update
or insert to keep two fields in sync.

.. code-block:: python

    class MyModel(models.Model):
        int_field = models.IntField()
        in_sync_int = models.IntField(help_text="Stays the same as int_field")

        class Meta:
            triggers = [
                pgtrigger.Trigger(
                    name="keep_in_sync",
                    operation=pgtrigger.Update | pgtrigger.Insert,
                    when=pgtrigger.Before,
                    func="NEW.in_sync_int = NEW.int_field; RETURN NEW;",
                )
            ]

.. note::

    When writing a `pgtrigger.Before` trigger, be sure to return the row over
    which the operation should be applied. Returning no row will prevent the
    operation from happening.
    See `the Postgres docs <https://www.postgresql.org/docs/current/plpgsql-trigger.html>`__
    for more information.

Soft-delete models
~~~~~~~~~~~~~~~~~~

Rather than fully deleting a model, one can "soft-delete" it by setting a
field to an inactive state. The `pgtrigger.SoftDelete` takes the field
as an argument and a value to set on delete, which defaults to ``False``.
For example:

.. code-block:: python

    class SoftDeleteModel(models.Model):
        # This field is set to false when the model is deleted
        is_active = models.BooleanField(default=True)

        class Meta:
            triggers = [
                pgtrigger.SoftDelete(name="soft_delete", field="is_active")
            ]


    m = SoftDeleteModel.objects.create()
    m.delete()

    # The model will still exist, but it is no longer active
    assert not SoftDeleteModel.objects.get().is_active

`pgtrigger.SoftDelete` works with nullable
``CharField``, ``IntField``, and ``BooleanField`` fields.

Let's extend this example with the assumption that we're mostly interested in 
active objects and don't want to see soft-deleted items when pulling data from
QuerySets. The addition of the custom Model Manager below along with changes to
SoftDeleteModel ensures that QuerySets using ``objects`` (e.g.,
``Foo.objects.all()``) will automatically filter out soft-deleted items and
only return active objects.

.. code-block:: python

    class NotDeletedManager(models.Manager):
    """Automatically filters out soft deleted objects from QuerySets"""
    
        def get_queryset(self):
            return (
                super(NotDeletedManager, self)
                .get_queryset()
                .filter(is_active=False)
            )
    
    
    class SoftDeleteModel(models.Model):
        # This field is set to false when the model is deleted
        is_active = models.BooleanField(default=True)
        
        all_objects = models.ModelManager()  # access deleted objects too
        objects = NotDeletedManager()  # filter out soft deleted objects

        class Meta:
            triggers = [
                pgtrigger.SoftDelete(name="soft_delete", field="is_active")
            ]
            # Return both active/deleted data via Django Admin, dumpdata, etc.
            default_manager_name = "all_objects"

We can still get to both the deleted and active items by using the
``all_objects`` Model Manager like so:

.. code-block:: python

    MyModelName.all_objects.all()

Please also note the addition of ``default_manager_name`` to Meta. This
attribute configures Django to use ``all_objects`` (i.e. the built-in
``models.Manager`` in this case) as its default Model Manager internally. This
allows access to soft deleted objects via the Django Admin Page, dumpdata, and
other Django internals.

.. note::

    When using `pgtrigger.SoftDelete`, keep in mind that Django will still
    perform cascading operations. For example, a foreign key to
    ``SoftDeleteModel`` with ``on_delete=models.CASCADE`` will be deleted
    by Django when the parent model is soft deleted.

Append-only models
~~~~~~~~~~~~~~~~~~

Here we create an append-only model using the `pgtrigger.Protect`
trigger for the ``UPDATE`` and ``DELETE`` operations:

.. code-block:: python

    class AppendOnlyModel(models.Model):
        my_field = models.IntField()

        class Meta:
            triggers = [
                pgtrigger.Protect(
                    name="append_only",
                    operation=(pgtrigger.Update | pgtrigger.Delete)
                )
            ]

.. note::

    This table can still be truncated. Although Django doesn't support this
    database operation, one can still protect against this by adding the
    `pgtrigger.Truncate` operation.

Official interfaces
~~~~~~~~~~~~~~~~~~~

`pgtrigger.Protect` triggers can be combined with `pgtrigger.ignore` to create
"official" interfaces for doing database operations in your application.

Here we protect inserts on our custom ``User`` model and force engineers
to use ``create_user`` to create them:

.. code-block:: python

    @pgtrigger.ignore("my_app.User:protect_inserts")
    def create_user(**kwargs):
        return User.objects.create(**kwargs)


    class User(models.Model):
        class Meta:
            triggers = [
                pgtrigger.Protect(name="protect_inserts", operation=pgtrigger.Insert)
            ]

We've ignored the protection trigger for the ``create_user`` function by providing
its full path to `pgtrigger.ignore`. All users must use ``create_user`` to create
``User`` objects, otherwise an exception will happen.

.. note::

    Ignoring triggers is covered in the
    :ref:`ignoring_triggers` section.

Conditional deletion protection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here we only allow models with a ``deletable`` flag to be deleted:

.. code-block:: python


    class DynamicDeletionModel(models.Model):
        is_deletable = models.BooleanField(default=False)

        class Meta:
            triggers = [
                pgtrigger.Protect(
                    name="protect_deletes",
                    operation=pgtrigger.Delete,
                    condition=pgtrigger.Q(old__is_deletable=False)
                )
            ]

Redundant update protection
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here we raise an error when someone makes a redundant update
to the database:

.. code-block:: python

    class RedundantUpdateModel(models.Model):
        redundant_field1 = models.BooleanField(default=False)
        redundant_field2 = models.BooleanField(default=False)

        class Meta:
            triggers = [
                pgtrigger.Protect(
                    name="protect_redundant_updates",
                    operation=pgtrigger.Update,
                    condition=pgtrigger.Condition(
                        "OLD.* IS NOT DISTINCT FROM NEW.*"
                    )
                )
            ]

Freezing published models
~~~~~~~~~~~~~~~~~~~~~~~~~

Here we have a ``Post`` model with a ``status`` field. We only allow edits to this model
when its ``status`` is not "published".

.. code-block::

    class Post(models.Model):
        status = models.CharField(default="unpublished")
        content = models.TextField()

        class Meta:
            triggers = [
                pgtrigger.Protect(
                    name="freeze_published_model",
                    operation=pgtrigger.Update,
                    condition=pgtrigger.Q(old__status="published")
                )
            ]

We extend this example by allowing a published model to be able to
be edited, but only when transitioning it to an "inactive" status.

.. code-block::

    class Post(models.Model):
        status = models.CharField(default="unpublished")
        content = models.TextField()

        class Meta:
            triggers = [
                pgtrigger.Protect(
                    name="freeze_published_model_allow_deactivation",
                    operation=pgtrigger.Update,
                    condition=(
                      pgtrigger.Q(old__status="published")
                      & ~pgtrigger.Q(new__status="inactive")
                )
            ]

Versioned models
~~~~~~~~~~~~~~~~

Here we write a `pgtrigger.Trigger` trigger
that dynamically increments a model version before an update is
applied.

We do this with two triggers:

1. One that protects updating the ``version`` field of the model. We don't
   want people tampering with this field.
2. A trigger that increments the ``version`` of the ``NEW`` row before
   an update is applied. We ignore updating the version if there are no changes.

.. code-block:: python

    class Versioned(models.Model):
        """
        This model is versioned. The "version" field is incremented on every
        update, and users cannot directly update the "version" field.
        """
        version = models.IntegerField(default=0)
        char_field = models.CharField(max_length=32)

        class Meta:
            triggers = [
                # Protect anyone editing the version field directly
                pgtrigger.Protect(
                    name="protect_updates",
                    operation=pgtrigger.Update,
                    condition=pgtrigger.Q(old__version__df=pgtrigger.F("new__version"))
                ),
                # Increment the version field on changes
                pgtrigger.Trigger(
                    name="versioning",
                    when=pgtrigger.Before,
                    operation=pgtrigger.Update,
                    func="NEW.version = NEW.version + 1; RETURN NEW;",
                    # Don't increment version on redundant updates.
                    condition=pgtrigger.Condition("OLD.* IS DISTINCT FROM NEW.*")
                )
            ]

.. note::

    The return value
    from `pgtrigger.Before` triggers is what Postgres uses when
    executing the operation. ``NULL`` values tell Postgres to ignore
    the operation entirely.

Keeping a search vector updated
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When using `Postgres full-text search <https://docs.djangoproject.com/en/4.0/ref/contrib/postgres/search/>`__,
keep ``django.contrib.postgres.search.SearchVectorField`` fields updated using `pgtrigger.UpdateSearchVector`.
Here we keep a search vector updated based on changes to the ``title`` and ``body`` fields of a model:

.. code-block:: python

    class DocumentModel(models.Model):
        search_vector = SearchVectorField()
        title = models.CharField(max_length=128)
        body = models.TextField()

        class Meta:
            triggers = [
                pgtrigger.UpdateSearchVector(
                    name="add_title_and_body_to_vector",
                    vector_field="search_vector",
                    document_fields=["title", "body"],
                )
            ]

`pgtrigger.UpdateSearchVector` uses Postgres's ``tsvector_update_trigger`` to keep
the search vector updated. See the `Postgres docs <https://www.postgresql.org/docs/current/textsearch-features.html#TEXTSEARCH-UPDATE-TRIGGERS>`__ for more info.

.. note::

    `pgtrigger.UpdateSearchVector` triggers are incompatible with `pgtrigger.ignore`
    and will raise a `RuntimeError` if used.

Statement-level triggers and transition tables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

So far most of the examples have been
for triggers that fire once per row. Statement-level triggers are fired
once per statement and allow more flexibility and performance tuning
for some scenarios. 

Instead of ``OLD`` and ``NEW`` rows, statement-level triggers can
use "transition tables" to access temporary tables of old and new rows.
One can use the `pgtrigger.Referencing` construct to configure this.
See `this StackExchange example <https://dba.stackexchange.com/a/177468>`__
for more explanations about transition tables.

.. note::

    Transition tables are only available in Postgres 10 and up.

Here we have a history model that keeps track of changes to
a field in the tracked model.
We create a statement-level trigger that logs the old and new
fields to the history model:

.. code-block:: python

    class HistoryModel(models.Model):
        old_field = models.CharField(max_length=32)
        new_field = models.CharField(max_length=32)


    class TrackedModel(models.Model):
        field = models.CharField(max_length=32)

        class Meta:
            triggers = [
                pgtrigger.Trigger(
                    name="track_history",
                    level=pgtrigger.Statement,
                    when=pgtrigger.After,
                    operation=pgtrigger.Update,
                    referencing=pgtrigger.Referencing(old="old_values", new="new_values"),
                    func=f"""
                        INSERT INTO {HistoryModel._meta.db_table}(old_field, new_field)
                        SELECT
                            old_values.field AS old_field,
                            new_values.field AS new_field
                        FROM old_values
                            JOIN new_values ON old_values.id = new_values.id;
                        RETURN NULL;
                    """,
                )
            ]


With this statement-level trigger, we have the benefit that only one additional query is performed,
even on bulk inserts to the tracked model. Here's some example code to illustrate what the results
look like.

.. code-block:: python

    TrackedModel.objects.bulk_create([LoggedModel(field='old'), LoggedModel(field='old')])

    # Update all fields to "new"
    TrackedModel.objects.update(field='new')

    # The trigger should have tracked these updates
    print(HistoryModel.values('old_field', 'new_field'))

    >>> [{
      'old_field': 'old',
      'new_field': 'new'
    }, {
      'old_field': 'old',
      'new_field': 'new'
    }]

.. note::

    When considering use of statment-level triggers for performance reasons, keep in mind that additional
    queries executed by triggers do not involve expensive round-trips from the application.
    A less-complex row-level trigger may be worth the performance cost.

Ensuring child models exist
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Consider a ``Profile`` model that has a ``OneToOne`` to Django's ``User`` model:

.. code-block:: python

    class Profile(models.Model):
        user = models.OneToOneField(User, on_delete=models.CASCADE)

We use a "deferrable" trigger to ensure a ``Profile`` exists for every ``User``.
Deferrable triggers can execute at the end of a transaction,
allowing us to check for the existence of a ``Profile`` after creating a
``User``.

This example is continued in the :ref:`deferrable` section.

Tracking model history and changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Check out `django-pghistory <https://django-pghistory.readthedocs.io>`__
to snapshot model changes and attach context from
your application (e.g. the authenticated user) to the event.

.. _func_model_properties:

Model properties in the func
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When writing triggers in the model ``Meta``, it's not possible
to access properties of the model like the database name or fields.
`pgtrigger.Func` solves this by exposing the following variables
you can use in a template string:

* **meta**: The ``._meta`` of the model.
* **fields**: The fields of the model, accessible as attributes.
* **columns**: The field columns. ``columns.field_name`` will return
  the database column of the ``field_name`` field.

For example, say that we have the following model and trigger:

.. code-block:: python

    class MyModel(models.Model):
        text_field = models.TextField()

        class Meta:
            triggers = [
                pgtrigger.Trigger(
                    func=pgtrigger.Func(
                        """
                        # This is only pseudocode
                        SELECT {columns.text_field} FROM {meta.db_table};
                        """
                    )
                )
            ]

Above the `pgtrigger.Func` references the table name of the model and the column
of ``text_field``.

.. note::

    Remember to escape curly bracket characters when using `pgtrigger.Func`.

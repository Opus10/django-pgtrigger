# Conditional Triggers

Here's a brief guide on the many ways one can create conditional row-level triggers using `django-pgtrigger`. We start with the high-level utilities and make our way towards lower-level ones.

Remember, row-level triggers have access to either the `NEW` row being inserted or updated, or the `OLD` row being updated or deleted. These variables are copies of the row and can be used in the conditions of the trigger. Updates triggers, for example, can conditionally execute based on both the values of the row before the update (the `OLD` row) and the row after the modification (the `NEW` row).

!!! note

    Consult the [Postgres docs](https://www.postgresql.org/docs/current/plpgsql-trigger.html) for more information on these variables.

We'll first dive into update-based triggers and the utilities `django-pgtrigger` provides for detecting changes on models.

## Field Change Conditions

The following conditions are provided out of the box for conveniently expressing field changes:

- [pgtrigger.AnyChange][]: If any supplied fields change, trigger the condition.
- [pgtrigger.AnyDontChange][]: If any supplied fields don't change, trigger the condition.
- [pgtrigger.AllChange][]: If all supplied fields change, trigger the condition.
- [pgtrigger.AllDontChange][]: If all supplied fields don't change, trigger the condition.

For example, let's use this model:

```python
class MyModel(models.Model):
    int_field = models.IntegerField()
    char_field = models.CharField(null=True)
    dt_field = models.DateTimeField(auto_now=True)
```

The following trigger will raise an exception if an update happens that doesn't change a single field.

```python
pgtrigger.Protect(operation=pgtrigger.Update, condition=~pgtrigger.AnyChange())
```

This is also equivalent to doing:

```python
pgtrigger.Protect(operation=pgtrigger.Update, condition=pgtrigger.AllDontChange())
```

!!! remember

    If no arguments are provided to any of these utilities, they operate over all fields on the model.

Let's say we want to block updates if any changes happen to the int or char fields:

```python
pgtrigger.Protect(
    operation=pgtrigger.Update,
    condition=pgtrigger.AnyChange("int_field", "char_field")
)
```

This is how the [pgtrigger.ReadOnly][] trigger is implemented. Underneath the hood, the condition looks like this:

```sql
OLD.int_field IS DISTINCT FROM NEW.int_field
OR OLD.char_field IS DISTINCT FROM NEW.char_field
```

!!! note

    `IS DISTINCT FROM` helps ensure that nullable objects are correctly compared since null never equals null.

One can also exclude fields in the condition. For example, this condition fires only if every field but the excluded ones change:

```python
pgtrigger.AllChange(exclude=["dt_field"])
```

To automatically ignore `auto_now` and `auto_now_add` datetime fields, do:

```python
# Fires on changes to any fields except auto_now and auto_now_add fields
pgtrigger.AnyChange(exclude_auto=True)
```

!!! remember

    Included and excluded fields can both be supplied. Included fields are used as the initial fields before `exclude` and `exclude_auto` remove fields.

## Targetting old and new fields with `pgtrigger.Q` and `pgtrigger.F`

We previously covered various change condition utilties. These only operate over update-based triggers. One can create fine-grained trigger conditions for all operations by using [pgtrigger.Q][] and [pgtrigger.F][] constructs.

For example, let's use our model from above again:

```python
class MyModel(models.Model):
    int_field = models.IntegerField()
    char_field = models.CharField(null=True)
    dt_field = models.DateTimeField(auto_now=True)
```

The following condition will fire whenever the old row has an `int_field` greater than zero:

```python
pgtrigger.Q(old__int_field__gt=0)
```

Similar to Django's syntax, the [pgtrigger.Q][] object can reference the `old__` and `new__` row. The [pgtrigger.F][] object can also be used for doing comparisons. For example, here we only fire when the `int_field` of the old row is greater than the int field of the new row.

```python
pgtrigger.Q(old__int_field__gt=pgtrigger.F("new__int_field"))
```

Remember to use the `__df` operator for `DISTINCT FROM` and `__ndf` for `NOT DISTINCT FROM`. This is generally the behavior one desires when checking for changes of nullable fields. For example, this condition fires only when `char_field` is not distinct from its old version.

```python
pgtrigger.Q(old__char_field__ndf=pgtrigger.F("new__char_field"))
```

!!! note

    The above is equivalent to doing `pgtrigger.AnyDontChange("char_field")`

Finally, [pgtrigger.Q][] objects can be negated, and-ed, and or-ed just like django `Q` objects:

```python
pgtrigger.Q(old__char_field__ndf=pgtrigger.F("new__char_field"))
| pgtrigger.Q(new__int_field=0)
```

## Raw SQL conditions

The utilities above should handle the majority of use cases when expressing conditions; however, users can still express raw SQL with [pgtrigger.Condition][]. For example, here's a condition that fires if any field changes:

```python
pgtrigger.Condition("OLD.* IS DISTINCT FROM NEW.*")
```

!!! note

    The above is equivalent to `pgtrigger.AnyChange()`.

## Conditions across multiple models

Remember, trigger conditions can only be expressed based on the rows of the current model. One can't, for example, reference a joined foreign key's value. This isn't a limitation in `django-pgtrigger` but rather a limitation in Postgres.

Custom conditional logic than spans multiple tables must happen inside the function as an `if/else` type of statement. [See this resource](https://www.postgresqltutorial.com/postgresql-plpgsql/plpgsql-if-else-statements/) for an example of what this looks like.

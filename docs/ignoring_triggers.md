# Ignoring Execution

[pgtrigger.ignore][] is a decorator and context manager that temporarily ignores triggers for a single
thread of execution. Here we ignore deletion protection:

```python
class CannotDelete(models.Model):
    class Meta:
        triggers = [
            pgtrigger.Protect(name="protect_deletes", operation=pgtrigger.Delete)
        ]


# Bypass deletion protection
with pgtrigger.ignore("my_app.CannotDelete:protect_deletes"):
    CannotDelete.objects.all().delete()
```

As shown above, [pgtrigger.ignore][] takes a trigger URI that is formatted as `{app_label}.{model_name}:{trigger_name}`. Multiple trigger URIs can be given to [pgtrigger.ignore][], and [pgtrigger.ignore][] can be nested. If no trigger URIs are provided to [pgtrigger.ignore][], all triggers are ignored.

!!! tip

    See all trigger URIs with `python manage.py pgtrigger ls`

By default, [pgtrigger.ignore][] configures ignoring triggers on every postgres database. This can be changed with the `databases` argument.

!!! important

    Remember, [pgtrigger.ignore][] ignores the execution of a trigger on a per-thread basis. This is very different from disabling a trigger or uninstalling a trigger globally. See the [Advanced Installation](advanced_installation.md) section for more details on managing the installation of triggers.

## Transaction notes

[pgtrigger.ignore][] flushes a temporary Postgres variable at the end of the context manager if running in a transaction. This could cause issues for transactions that are in an errored state.

Here's an example of when this case happens:

```python
with transaction.atomic():
    with ptrigger.ignore("app.Model:protect_inserts"):
        try:
            # Create an object that raises an integrity error
            app.Model.objects.create(unique_key="duplicate")
        except IntegrityError:
            # Ignore the integrity error
            pass

    # When we exit the context manager here, it will try to flush
    # a local Postgres variable. This causes an error because the transaction
    # is in an errored state.
```

If you're ignoring triggers and handling database errors, there are two ways to prevent this error from happening:

1. Wrap the outer transaction in `with pgtrigger.ignore.session():` so that the session is completed outside the transaction.
2. Wrap the inner `try/except` in `with transaction.atomic():` so that the errored part of the transaction is rolled back before the [pgtrigger.ignore][] context manager ends.


## Ignore other triggers within a trigger

Provide an `ignore_others` list of trigger URIs you would like to ignore while executing
a certain trigger. See the example below for details:

The `increment_comment_count` trigger will update the `comment_count` on a topic, instead of calculating
the count each time a topic is queried. Let's assume you are fixing a Justin Bieber Instagram
[bug](https://www.wired.com/2015/11/how-instagram-solved-its-justin-bieber-problem/). However we have
also protected the `comment_count` with a `pgtrigger.ReadOnly(name='read_only_comment_count')` trigger.

In this case you would provide a `ignore_others=['tests.Topic:read_only_comment_count']` to the
`increment_comment_count` trigger.

```python
class Topic(models.Model):
    name = models.CharField(max_length=100)
    comment_count = models.PositiveIntegerField(default=0)

    class Meta:
        triggers = [
            pgtrigger.ReadOnly(
                name='read_only_comment_count',
                fields=['comment_count']
            )
        ]


class Comment(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    # Other fields

    class Meta:
        triggers = [
            pgtrigger.Trigger(
                func=pgtrigger.Func(
                    '''
                    UPDATE "{db_table}"
                        SET "{comment_count}" = "{comment_count}" + 1
                    WHERE
                        "{db_table}"."{topic_pk}" = NEW."{columns.topic}";
                    {reset_ignore}
                    RETURN NEW;
                    ''',
                    db_table = Topic._meta.db_table,
                    comment_count = Topic._meta.get_field('comment_count').get_attname_column()[1],
                    topic_pk = Topic._meta.pk.get_attname_column()[1]                   
                ),    
                ignore_others=['tests.Topic:read_only_comment_count'],
                when=pgtrigger.Before,
                operation=pgtrigger.Insert,
                name='increment_comment_count'
            ),
        ]
```

!!! important

    Remember to use the `{reset_ignore}` placeholder in the trigger function before you return
    from any branch. Without it the triggers you have ignored will persist throughout the session.

It is mandatory to provide an instace of `pgtrigger.Func` to the `func` parameter.
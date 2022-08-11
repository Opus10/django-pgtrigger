import collections
import contextlib
import copy
import inspect
import logging
import threading

import django.apps
from django.conf import settings
from django.db import connections, DEFAULT_DB_ALIAS, models, router
from django.db.models.expressions import Col
from django.db.models.fields.related import RelatedField
from django.db.models.sql import Query
from django.db.models.sql.datastructures import BaseTable
import psycopg2.extensions

import pgtrigger.features
import pgtrigger.registry


# The core pgtrigger logger
LOGGER = logging.getLogger('pgtrigger')

# Postgres only allows identifiers to be 63 chars max. Since "pgtrigger_"
# is the prefix for trigger names, and since an additional "_" and
# 5 character hash is added, the user-defined name of the trigger can only
# be 47 chars.
# NOTE: We can do something more sophisticated later by allowing users
# to name their triggers and then hashing the names when actually creating
# the triggers.
MAX_NAME_LENGTH = 47

# Installation states for a triggers
INSTALLED = 'INSTALLED'
UNINSTALLED = 'UNINSTALLED'
OUTDATED = 'OUTDATED'
PRUNE = 'PRUNE'

# All triggers currently being ignored
_ignore = threading.local()

# A sentinel value to determine if a kwarg is unset
_unset = object()


def _quote(label):
    """Conditionally wraps a label in quotes"""
    if label.startswith('"'):
        return label
    else:
        return f'"{label}"'


def _get_database(model):
    """
    Obtains the database used for a trigger / model pair. The database
    for the connection is selected based on the write DB in the database
    router config.
    """
    return router.db_for_write(model) or DEFAULT_DB_ALIAS


def _postgres_databases(databases):
    """Given an iterable of databases, only return postgres ones"""
    return [database for database in databases if connections[database].vendor == 'postgresql']


def _get_connection(model):
    """
    Obtains the connection used for a trigger / model pair. The database
    for the connection is selected based on the write DB in the database
    router config.
    """
    return connections[_get_database(model)]


def _get_model(table):
    """Obtains a django model based on its table name"""
    for model in django.apps.apps.get_models():  # pragma: no branch
        if _quote(model._meta.db_table) == _quote(table) and not model._meta.proxy:
            return model


def _is_concurrent_statement(sql):
    """
    True if the sql statement is concurrent and cannot be ran in a transaction
    """
    sql = sql.strip().lower() if sql else ''
    return sql.startswith('create') and 'concurrently' in sql


def _is_transaction_errored(cursor):
    """
    True if the current transaction is in an errored state
    """
    return (
        cursor.connection.get_transaction_status()
        == psycopg2.extensions.TRANSACTION_STATUS_INERROR
    )


def _inject_pgtrigger_ignore(execute, sql, params, many, context):  # pragma: no cover
    """
    A connection execution wrapper that sets a pgtrigger.ignore
    variable in the executed SQL. This lets other triggers know when
    they should ignore execution
    """
    cursor = context['cursor']

    # A named cursor automatically prepends
    # "NO SCROLL CURSOR WITHOUT HOLD FOR" to the query, which
    # causes invalid SQL to be generated. There is no way
    # to override this behavior in psycopg2, so ignoring triggers
    # cannot happen for named cursors. Django only names cursors
    # for iterators and other statements that read the database,
    # so it seems to be safe to ignore named cursors.
    #
    # Concurrent index creation is also incompatible with local variable
    # setting. Ignore these cases for now.
    if (
        not cursor.name
        and not _is_concurrent_statement(sql)
        and not _is_transaction_errored(cursor)
    ):
        sql = "SET LOCAL pgtrigger.ignore='{" + ",".join(_ignore.value) + "}';" + sql

    return execute(sql, params, many, context)


def register(*triggers):
    """
    Register the given triggers with wrapped Model class.

    Args:
        *triggers (`pgtrigger.Trigger`): Trigger classes to register.

    Examples:
        Register by decorating a model::

            @pgtrigger.register(
                pgtrigger.Protect(
                    name="append_only",
                    operation=(pgtrigger.Update | pgtrigger.Delete)
                )
            )
            class MyModel(models.Model):
                pass

        Register by calling functionally::

            pgtrigger.register(trigger_object)(MyModel)
    """

    def _model_wrapper(model_class):
        for trigger in triggers:
            trigger.register(model_class)

        return model_class

    return _model_wrapper


class _Serializable:
    def get_init_vals(self):
        """Returns class initialization args so that they are properly serialized for migrations"""
        parameters = inspect.signature(self.__init__).parameters

        for key, val in parameters.items():
            if key != "self" and (
                not hasattr(self, key) or val.kind == inspect.Parameter.VAR_KEYWORD
            ):  # pragma: no cover
                raise ValueError(
                    f"Could not automatically serialize Trigger {self.__class__} for migrations."
                    ' Implement "get_init_vals()" on the trigger class. See the'
                    ' FAQ in the django-pgtrigger docs for more information.'
                )

        args = tuple(
            item
            for key, val in parameters.items()
            if val.kind == inspect.Parameter.VAR_POSITIONAL
            for item in getattr(self, key)
        )

        kwargs = {
            key: getattr(self, key)
            for key, value in parameters.items()
            if key != "self" and val.kind != inspect.Parameter.VAR_POSITIONAL
        }

        return args, kwargs

    def deconstruct(self):
        """For supporting Django migrations"""
        path = f"{self.__class__.__module__}.{self.__class__.__name__}"
        path = path.replace("pgtrigger.core", "pgtrigger")
        args, kwargs = self.get_init_vals()
        return path, args, kwargs

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.get_init_vals() == other.get_init_vals()


class _Primitive(_Serializable):
    """Boilerplate for some of the primitive operations"""

    def __init__(self, name):
        assert name in self.values
        self.name = name

    def __str__(self):
        return self.name


class Level(_Primitive):
    values = ("ROW", "STATEMENT")


#: For specifying row-level triggers (the default)
Row = Level('ROW')

#: For specifying statement-level triggers
Statement = Level('STATEMENT')


class Referencing(_Serializable):
    """For specifying the REFERENCING clause of a statement-level trigger"""

    def __init__(self, *, old=None, new=None):
        if not old and not new:
            raise ValueError(
                'Must provide either "old" and/or "new" to the referencing'
                ' construct of a trigger'
            )

        self.old = old
        self.new = new

    def __str__(self):
        ref = 'REFERENCING'
        if self.old:
            ref += f' OLD TABLE AS {self.old} '

        if self.new:
            ref += f' NEW TABLE AS {self.new} '

        return ref


class When(_Primitive):
    values = ("BEFORE", "AFTER", "INSTEAD OF")


#: For specifying ``BEFORE`` in the when clause of a trigger.
Before = When('BEFORE')

#: For specifying ``AFTER`` in the when clause of a trigger.
After = When('AFTER')

#: For specifying ``INSTEAD OF`` in the when clause of a trigger.
InsteadOf = When('INSTEAD OF')


class Operation(_Primitive):
    values = ("UPDATE", "DELETE", "TRUNCATE", "INSERT")

    def __or__(self, other):
        assert isinstance(other, Operation)
        return Operations(self, other)


class Operations(Operation):
    """For providing multiple operations ``OR``ed together.

    Note that using the ``|`` operator is preferred syntax.
    """

    def __init__(self, *operations):
        for operation in operations:
            assert isinstance(operation, Operation)

        self.operations = operations

    def __str__(self):
        return ' OR '.join(str(operation) for operation in self.operations)


#: For specifying ``UPDATE`` as the trigger operation.
Update = Operation('UPDATE')

#: For specifying ``DELETE`` as the trigger operation.
Delete = Operation('DELETE')

#: For specifying ``TRUNCATE`` as the trigger operation.
Truncate = Operation('TRUNCATE')

#: For specifying ``INSERT`` as the trigger operation.
Insert = Operation('INSERT')


class UpdateOf(Operation):
    """For specifying ``UPDATE OF`` as the trigger operation."""

    def __init__(self, *columns):
        if not columns:
            raise ValueError('Must provide at least one column')

        self.columns = columns

    def __str__(self):
        columns = ', '.join(f'{_quote(col)}' for col in self.columns)
        return f'UPDATE OF {columns}'


class Timing(_Primitive):
    values = ("IMMEDIATE", "DEFERRED")


#: For deferrable triggers that run immediately by default
Immediate = Timing('IMMEDIATE')

#: For deferrable triggers that run at the end of the transaction by default
Deferred = Timing('DEFERRED')


class Condition(_Serializable):
    """For specifying free-form SQL in the condition of a trigger."""

    sql = None

    def __init__(self, sql=None):
        self.sql = sql or self.sql

        if not self.sql:
            raise ValueError('Must provide SQL to condition')

    def resolve(self, model):
        return self.sql


class _OldNewQuery(Query):
    """
    A special Query object for referencing the ``OLD`` and ``NEW`` variables in a
    trigger. Only used by the `pgtrigger.Q` object.
    """

    def build_lookup(self, lookups, lhs, rhs):
        # Django does not allow custom lookups on foreign keys, even though
        # DISTINCT FROM is a comnpletely valid lookup. Trick django into
        # being able to apply this lookup to related fields.
        if lookups == ['df'] and isinstance(lhs.output_field, RelatedField):
            lhs = copy.deepcopy(lhs)
            lhs.output_field = models.IntegerField(null=lhs.output_field.null)

        return super().build_lookup(lookups, lhs, rhs)

    def build_filter(self, filter_expr, *args, **kwargs):
        if isinstance(filter_expr, Q):
            return super().build_filter(filter_expr, *args, **kwargs)

        if filter_expr[0].startswith('old__'):
            alias = 'OLD'
        elif filter_expr[0].startswith('new__'):
            alias = 'NEW'
        else:  # pragma: no cover
            raise ValueError('Filter expression on trigger.Q object must reference old__ or new__')

        filter_expr = (filter_expr[0][5:], filter_expr[1])
        node, _ = super().build_filter(filter_expr, *args, **kwargs)

        self.alias_map[alias] = BaseTable(alias, alias)
        for child in node.children:
            child.lhs = Col(
                alias=alias,
                target=child.lhs.target,
                output_field=child.lhs.output_field,
            )

        return node, {alias}


class F(models.F):
    """
    Similar to Django's ``F`` object, allows referencing the old and new
    rows in a trigger condition.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.name.startswith('old__'):
            self.row_alias = 'OLD'
        elif self.name.startswith('new__'):
            self.row_alias = 'NEW'
        else:
            raise ValueError('F() values must reference old__ or new__')

        self.col_name = self.name[5:]

    def deconstruct(self):
        path, args, kwargs = super().deconstruct()
        path = path.replace("pgtrigger.core", "pgtrigger")
        return path, args, kwargs

    @property
    def resolved_name(self):
        return f'{self.row_alias}.{_quote(self.col_name)}'

    def resolve_expression(self, query=None, *args, **kwargs):
        return Col(
            alias=self.row_alias,
            target=query.model._meta.get_field(self.col_name),
        )


@models.fields.Field.register_lookup
class IsDistinctFrom(models.Lookup):
    """
    A custom ``IS DISTINCT FROM`` field lookup for common trigger conditions.
    For example, ``pgtrigger.Q(old__field__df=pgtrigger.F("new__field"))``.
    """

    lookup_name = 'df'

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        return '%s IS DISTINCT FROM %s' % (lhs, rhs), params


@models.fields.Field.register_lookup
class IsNotDistinctFrom(models.Lookup):
    """
    A custom ``IS NOT DISTINCT FROM`` field lookup for common trigger conditions.
    For example, ``pgtrigger.Q(old__field__ndf=pgtrigger.F("new__field"))``.
    """

    lookup_name = 'ndf'

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        return '%s IS NOT DISTINCT FROM %s' % (lhs, rhs), params


class Q(models.Q, Condition):
    """
    Similar to Django's ``Q`` object, allows referencing the old and new
    rows in a trigger condition.
    """

    def deconstruct(self):
        path, args, kwargs = super().deconstruct()
        path = path.replace("pgtrigger.core", "pgtrigger")
        return path, args, kwargs

    def resolve(self, model):
        connection = _get_connection(model)
        query = _OldNewQuery(model)
        sql = (
            connection.cursor()
            .mogrify(
                *self.resolve_expression(query).as_sql(
                    compiler=query.get_compiler('default'),
                    connection=connection,
                )
            )
            .decode()
            .replace('"OLD"', 'OLD')
            .replace('"NEW"', 'NEW')
        )

        return sql


def _render_uninstall(table, trigger_pgid):
    return f'DROP TRIGGER IF EXISTS {trigger_pgid} ON {_quote(table)};'


def _drop_trigger(table, trigger_pgid):
    model = _get_model(table)
    connection = _get_connection(model)
    uninstall_sql = _render_uninstall(table, trigger_pgid)
    with connection.cursor() as cursor:
        cursor.execute(uninstall_sql)


# Allows Trigger methods to be used as context managers, mostly for
# testing purposes
@contextlib.contextmanager
def _cleanup_on_exit(cleanup):
    yield
    cleanup()


def _render_ignore_func():
    """
    Triggers can be ignored dynamically by help of a special function that's installed.
    The definition of this function is here.

    Note: This function is global and shared by all triggers in the current
    implementation. It isn't uninstalled when triggers are uninstalled.
    """
    return '''
        CREATE OR REPLACE FUNCTION _pgtrigger_should_ignore(
            table_name NAME,
            trigger_name NAME
        )
        RETURNS BOOLEAN AS $$
            DECLARE
                _pgtrigger_ignore TEXT[];
                _result BOOLEAN;
            BEGIN
                BEGIN
                    SELECT INTO _pgtrigger_ignore
                        CURRENT_SETTING('pgtrigger.ignore');
                    EXCEPTION WHEN OTHERS THEN
                END;
                IF _pgtrigger_ignore IS NOT NULL THEN
                    SELECT CONCAT(table_name, ':', trigger_name) = ANY(_pgtrigger_ignore)
                    INTO _result;
                    RETURN _result;
                ELSE
                    RETURN FALSE;
                END IF;
            END;
        $$ LANGUAGE plpgsql;
    '''


def get(*uris, database=None):
    """
    Get registered trigger objects.

    Args:
        *uris (str): URIs of triggers to get. If none are provided,
            all triggers are returned. URIs are in the format of
            ``{app_label}.{model_name}:{trigger_name}``.
        database (str, default=None): Only get triggers from this
            database.

    Returns:
        List[`pgtrigger.Trigger`]: Matching trigger objects.
    """
    registry = pgtrigger.registry.get()

    if database and uris:
        raise ValueError('Cannot supply both trigger URIs and a database')

    if not database:
        databases = {_get_database(model) for model, _ in registry.values()}
    else:
        databases = [database] if isinstance(database, str) else database

    if uris:
        for uri in uris:
            if uri and len(uri.split(':')) == 1:
                raise ValueError(
                    'Trigger URI must be in the format of "app_label.model_name:trigger_name"'
                )
            elif uri and uri not in registry:
                raise ValueError(f'URI "{uri}" not found in pgtrigger registry')

        return [registry[uri] for uri in uris]
    else:
        return [
            (model, trigger)
            for model, trigger in registry.values()
            if _get_database(model) in databases
        ]


def install(*uris, database=None):
    """
    Install triggers.

    Args:
        *uris (str): URIs of triggers to install. If none are provided,
            all triggers are installed and orphaned triggers are pruned.
        database (str, default=None): Only install triggers from this
            database.
    """
    if uris:
        model_triggers = get(*uris, database=database)
    else:
        model_triggers = [
            (model, trigger)
            for model, trigger in get(database=database)
            if trigger.get_installation_status(model)[0] != INSTALLED
        ]

    for model, trigger in model_triggers:
        LOGGER.info(
            f'pgtrigger: Installing {trigger} trigger'
            f' for {model._meta.db_table} table'
            f' on {_get_database(model)} database.'
        )
        trigger.install(model)

    if not uris:  # pragma: no branch
        prune(database=database)


def get_prune_list(database=None):
    """Return triggers that will be pruned upon next full install

    Args:
        database (str, default=None): Only return results from this
            database. Defaults to returning results from all databases
    """
    installed = {
        (_quote(model._meta.db_table), trigger.get_pgid(model)) for model, trigger in get()
    }

    if isinstance(database, str):
        databases = [database]
    else:
        databases = database or settings.DATABASES

    prune_list = []
    for database in _postgres_databases(databases):
        with connections[database].cursor() as cursor:
            cursor.execute(
                'SELECT tgrelid::regclass, tgname, tgenabled'
                '    FROM pg_trigger'
                '    WHERE tgname LIKE \'pgtrigger_%\''
            )
            triggers = set(cursor.fetchall())

        prune_list += [
            (trigger[0], trigger[1], trigger[2] == 'O', database)
            for trigger in triggers
            if (_quote(trigger[0]), trigger[1]) not in installed
        ]

    return prune_list


def prune(database=None):
    """
    Remove any pgtrigger triggers in the database that are not used by models.
    I.e. if a model or trigger definition is deleted from a model, ensure
    it is removed from the database

    Args:
        database (str, default=None): Only prune triggers from this
            database.
    """
    for trigger in get_prune_list(database=database):
        LOGGER.info(
            f'pgtrigger: Pruning trigger {trigger[1]}'
            f' for table {trigger[0]} on {trigger[3]} database.'
        )
        _drop_trigger(trigger[0], trigger[1])


def enable(*uris, database=None):
    """
    Enables registered triggers.

    Args:
        *uris (str): URIs of triggers to enable. If none are provided,
            all triggers are enabled.
        database (str, default=None): Only enable triggers from this
            database.
    """
    if uris:
        model_triggers = get(*uris, database=database)
    else:
        model_triggers = [
            (model, trigger)
            for model, trigger in get(database=database)
            if trigger.get_installation_status(model)[1] is False
        ]

    for model, trigger in model_triggers:
        LOGGER.info(
            f'pgtrigger: Enabling {trigger} trigger'
            f' for {model._meta.db_table} table'
            f' on {_get_database(model)} database.'
        )
        trigger.enable(model)


def uninstall(*uris, database=None):
    """
    Uninstalls triggers.

    Args:
        *uris (str): URIs of triggers to uninstall. If none are provided,
            all triggers are uninstalled and orphaned triggers are pruned.
        database (str, default=None): Only uninstall triggers from this
            database.
    """
    if uris:
        model_triggers = get(*uris, database=database)
    else:
        model_triggers = [
            (model, trigger)
            for model, trigger in get(database=database)
            if trigger.get_installation_status(model)[0] != UNINSTALLED
        ]

    for model, trigger in model_triggers:
        LOGGER.info(
            f'pgtrigger: Uninstalling {trigger} trigger'
            f' for {model._meta.db_table} table'
            f' on {_get_database(model)} database.'
        )
        trigger.uninstall(model)

    if not uris:
        prune(database=database)


def disable(*uris, database=None):
    """
    Disables triggers.

    Args:
        *uris (str): URIs of triggers to disable. If none are provided,
            all triggers are disabled.
        database (str, default=None): Only disable triggers from this
            database.
    """
    if uris:
        model_triggers = get(*uris, database=database)
    else:
        model_triggers = [
            (model, trigger)
            for model, trigger in get(database=database)
            if trigger.get_installation_status(model)[1]
        ]

    for model, trigger in model_triggers:
        LOGGER.info(
            f'pgtrigger: Disabling {trigger} trigger for'
            f' {model._meta.db_table} table'
            f' on {_get_database(model)} database.'
        )
        trigger.disable(model)


def constraints(timing, *uris):
    """
    Set deferrable constraint timing for the given triggers, which
    will persist until overridden or until end of transaction.
    Must be in a transaction to run this.

    Args:
        timing (``pgtrigger.Timing``): The timing value that overrides
            the default trigger timing.
        *uris (str): Trigger URIs over which to set constraint timing.
            If none are provided, all trigger constraint timing will
            be set. All triggers must be deferrable.

    Raises:
        RuntimeError: If the database of any triggers is not in a transaction.
        ValueError: If any triggers are not deferrable.
    """

    model_triggers_by_db = collections.defaultdict(list)
    for model, trigger in get(*uris):
        if not trigger.timing:
            raise ValueError(
                f"Trigger {trigger.name} on model {model._meta.label_lower} is not deferrable."
            )

        model_triggers_by_db[_get_database(model)].append((model, trigger))

    for db, model_triggers in model_triggers_by_db.items():
        if not connections[db].in_atomic_block:
            raise RuntimeError(f"Database {db} is not in a transaction.")

        names = ', '.join(trigger.get_pgid(model) for model, trigger in model_triggers)

        with connections[db].cursor() as cursor:
            cursor.execute(f'SET CONSTRAINTS {names} {timing}')


@contextlib.contextmanager
def ignore(*uris):
    """
    Dynamically ignore registered triggers matching URIs from executing in
    an individual thread.
    If no URIs are provided, ignore all pgtriggers from executing in an
    individual thread.

    Args:
        *uris (str): Trigger URIs to ignore. If none are provided, all
            triggers will be ignored.

    Examples:

        Ingore triggers in a context manager::

            with pgtrigger.ignore("my_app.Model:trigger_name"):
                # Do stuff while ignoring trigger

        Ignore multiple triggers as a decorator::

            @pgtrigger.ignore("my_app.Model:trigger_name", "my_app.Model:other_trigger")
            def my_func():
                # Do stuff while ignoring trigger
    """
    with contextlib.ExitStack() as stack:
        for model, trigger in get(*uris):
            stack.enter_context(trigger.ignore(model))

        yield

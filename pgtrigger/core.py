import contextlib
import copy
import hashlib
import inspect
import logging
import threading

import django.apps
from django.conf import settings
from django.db import connections, DEFAULT_DB_ALIAS, models, router, transaction
from django.db.models.expressions import Col
from django.db.models.fields.related import RelatedField
from django.db.models.sql import Query
from django.db.models.sql.datastructures import BaseTable
from django.db.utils import ProgrammingError
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


class Trigger(_Serializable):
    """
    For specifying a free-form PL/pgSQL trigger function or for
    creating derived trigger classes.
    """

    name = None
    level = Row
    when = None
    operation = None
    condition = None
    referencing = None
    func = None
    declare = None

    def __init__(
        self,
        *,
        name=None,
        level=None,
        when=None,
        operation=None,
        condition=None,
        referencing=None,
        func=None,
        declare=None,
    ):
        self.name = name or self.name
        self.level = level or self.level
        self.when = when or self.when
        self.operation = operation or self.operation
        self.condition = condition or self.condition
        self.referencing = referencing or self.referencing
        self.func = func or self.func
        self.declare = declare or self.declare

        if not self.level or not isinstance(self.level, Level):
            raise ValueError(f'Invalid "level" attribute: {self.level}')

        if not self.when or not isinstance(self.when, When):
            raise ValueError(f'Invalid "when" attribute: {self.when}')

        if not self.operation or not isinstance(self.operation, Operation):
            raise ValueError(f'Invalid "operation" attribute: {self.operation}')

        if self.level == Row and self.referencing:
            raise ValueError('Row-level triggers cannot have a "referencing" attribute')

        if not self.name:
            raise ValueError('Trigger must have "name" attribute')

        self.validate_name()

    def __str__(self):
        return self.name

    def validate_name(self):
        """Verifies the name is under the maximum length"""
        if len(self.name) > MAX_NAME_LENGTH:
            raise ValueError(f'Trigger name "{self.name}" > {MAX_NAME_LENGTH} characters.')

    def get_pgid(self, model):
        """The ID of the trigger and function object in postgres

        All objects are prefixed with "pgtrigger_" in order to be
        discovered/managed by django-pgtrigger
        """
        model_hash = hashlib.sha1(self.get_uri(model).encode()).hexdigest()[:5]
        pgid = f'pgtrigger_{self.name}_{model_hash}'

        if len(pgid) > 63:
            raise ValueError(f'Trigger identifier "{pgid}" is greater than 63 chars')

        # NOTE - Postgres always stores names in lowercase. Ensure that all
        # generated IDs are lowercase so that we can properly do installation
        # and pruning tasks.
        return pgid.lower()

    def get_condition(self, model):
        return self.condition

    def get_declare(self, model):
        """
        Gets the DECLARE part of the trigger function if any variables
        are used.

        Returns:
            List[tuple]: A list of variable name / type tuples that will
            be shown in the DECLARE. For example [('row_data', 'JSONB')]
        """
        return self.declare or []

    def get_func(self, model):
        """
        Returns the trigger function that comes between the BEGIN and END
        clause
        """
        if not self.func:
            raise ValueError('Must define func attribute or implement get_func')
        return self.func

    def get_uri(self, model):
        """The URI for the trigger"""

        return f'{model._meta.app_label}.{model._meta.object_name}:{self.name}'

    def register(self, *models):
        """Register model classes with the trigger"""
        registry = pgtrigger.registry.get()

        for model in models:
            registry[self.get_uri(model)] = (model, self)

            # Add the trigger to Meta.triggers.
            # Note, pgtrigger's App.ready() method auto-registers any
            # triggers in Meta already, meaning the trigger may already exist. If so, ignore it
            if pgtrigger.features.migrations():  # pragma: no branch
                if self not in getattr(model._meta, "triggers", []):
                    model._meta.triggers = list(getattr(model._meta, "triggers", [])) + [self]

                if self not in model._meta.original_attrs.get("triggers", []):
                    model._meta.original_attrs["triggers"] = list(
                        model._meta.original_attrs.get("triggers", [])
                    ) + [self]

        return _cleanup_on_exit(lambda: self.unregister(*models))

    def unregister(self, *models):
        """Unregister model classes with the trigger"""
        registry = pgtrigger.registry.get()

        for model in models:
            del registry[self.get_uri(model)]

        # If we support migration integration, remove from Meta triggers
        if pgtrigger.features.migrations():  # pragma: no branch
            model._meta.triggers.remove(self)
            model._meta.original_attrs["triggers"].remove(self)

        return _cleanup_on_exit(lambda: self.register(*models))

    def render_condition(self, model):
        """Renders the condition SQL in the trigger declaration"""
        condition = self.get_condition(model)
        resolved = condition.resolve(model).strip() if condition else ''

        if resolved:
            if not resolved.startswith('('):
                resolved = f'({resolved})'
            resolved = f'WHEN {resolved}'

        return resolved

    def render_declare(self, model):
        """Renders the DECLARE of the trigger function, if any"""
        declare = self.get_declare(model)
        if declare:
            rendered_declare = 'DECLARE \n' + '\n'.join(
                f'{var_name} {var_type};' for var_name, var_type in declare
            )
        else:
            rendered_declare = ''

        return rendered_declare

    def render_ignore(self, model):
        """
        Renders the clause that can dynamically ignore the trigger's execution
        """
        return '''
            IF (_pgtrigger_should_ignore(TG_TABLE_NAME, TG_NAME) IS TRUE) THEN
                IF (TG_OP = 'DELETE') THEN
                    RETURN OLD;
                ELSE
                    RETURN NEW;
                END IF;
            END IF;
        '''

    def render_func(self, model):
        """Renders the trigger function SQL statement"""
        return f'''
            CREATE OR REPLACE FUNCTION {self.get_pgid(model)}()
            RETURNS TRIGGER AS $$
                {self.render_declare(model)}
                BEGIN
                    {self.render_ignore(model)}
                    {self.get_func(model)}
                END;
            $$ LANGUAGE plpgsql;
        '''

    def render_trigger(self, model):
        """Renders the trigger declaration SQL statement"""
        table = model._meta.db_table
        pgid = self.get_pgid(model)
        return f'''
            DROP TRIGGER IF EXISTS {pgid} on {_quote(table)};
            CREATE TRIGGER {pgid}
                {self.when} {self.operation} ON {_quote(table)}
                {self.referencing or ''}
                FOR EACH {self.level} {self.render_condition(model)}
                EXECUTE PROCEDURE {pgid}();
        '''

    def render_comment(self, model):
        """Renders the trigger commment SQL statement

        pgtrigger comments the hash of the trigger in order for us to
        determine if the trigger definition has changed
        """
        pgid = self.get_pgid(model)
        hash = self.get_hash(model)
        table = model._meta.db_table
        return f"COMMENT ON TRIGGER {pgid} ON {_quote(table)} IS '{hash}'"

    def get_installation_status(self, model):
        """Returns the installation status of a trigger.

        The return type is (status, enabled), where status is one of:

        1. ``INSTALLED``: If the trigger is installed
        2. ``UNINSTALLED``: If the trigger is not installed
        3. ``OUTDATED``: If the trigger is installed but
           has been modified

        "enabled" is True if the trigger is installed and enabled or false
        if installed and disabled (or uninstalled).
        """
        connection = _get_connection(model)
        trigger_exists_sql = f'''
            SELECT oid, obj_description(oid) AS hash, tgenabled AS enabled
            FROM pg_trigger
            WHERE tgname='{self.get_pgid(model)}'
                  AND tgrelid='{model._meta.db_table}'::regclass;
        '''
        try:
            with connection.cursor() as cursor:
                cursor.execute(trigger_exists_sql)
                results = cursor.fetchall()
        except ProgrammingError:  # pragma: no cover
            # When the table doesn't exist yet, possibly because migrations
            # haven't been executed, a ProgrammingError will happen because
            # of an invalid regclass cast. Return 'UNINSTALLED' for this
            # case
            return (UNINSTALLED, None)

        if not results:
            return (UNINSTALLED, None)
        else:
            hash = self.get_hash(model)
            if hash != results[0][1]:
                return (OUTDATED, results[0][2] == 'O')
            else:
                return (INSTALLED, results[0][2] == 'O')

    def get_hash(self, model):
        """
        Computes a hash for the trigger, which is used to
        uniquely identify its contents. The hash is computed based
        on the trigger function and declaration.

        Note: If the trigger definition includes dynamic data, such
        as the current time, the trigger hash will always change and
        appear to be out of sync.
        """
        rendered_func = self.render_func(model)
        rendered_trigger = self.render_trigger(model)
        return hashlib.sha1(f'{rendered_func} {rendered_trigger}'.encode()).hexdigest()

    def render_install(self, model):
        ignore_func = _render_ignore_func()
        rendered_func = self.render_func(model)
        rendered_trigger = self.render_trigger(model)
        rendered_comment = self.render_comment(model)

        return f"{ignore_func}; {rendered_func}; {rendered_trigger}; {rendered_comment};"

    def install(self, model):
        """Installs the trigger for a model"""
        connection = _get_connection(model)
        install_sql = self.render_install(model)
        with connection.cursor() as cursor:
            cursor.execute(install_sql)

        return _cleanup_on_exit(lambda: self.uninstall(model))

    def render_uninstall(self, model):
        return _render_uninstall(model._meta.db_table, self.get_pgid(model))

    def uninstall(self, model):
        """Uninstalls the trigger for a model"""
        connection = _get_connection(model)
        uninstall_sql = self.render_uninstall(model)
        with connection.cursor() as cursor:
            cursor.execute(uninstall_sql)

        return _cleanup_on_exit(lambda: self.install(model))  # pragma: no branch

    def enable(self, model):
        """Enables the trigger for a model"""
        connection = _get_connection(model)

        with connection.cursor() as cursor:
            cursor.execute(
                f'ALTER TABLE {_quote(model._meta.db_table)}'
                f' ENABLE TRIGGER {self.get_pgid(model)};'
            )

        return _cleanup_on_exit(lambda: self.disable(model))  # pragma: no branch

    def disable(self, model):
        """Disables the trigger for a model"""
        connection = _get_connection(model)

        with connection.cursor() as cursor:
            cursor.execute(
                f'ALTER TABLE {_quote(model._meta.db_table)}'
                f' DISABLE TRIGGER {self.get_pgid(model)};'
            )

        return _cleanup_on_exit(lambda: self.enable(model))  # pragma: no branch

    @contextlib.contextmanager
    def ignore(self, model):
        """Ignores the trigger in a single thread of execution"""
        connection = transaction.get_connection()

        with contextlib.ExitStack() as pre_execute_hook:

            # Create the table name / trigger name URI to pass down to the
            # trigger.
            ignore_uri = f'{model._meta.db_table}:{self.get_pgid(model)}'

            if not hasattr(_ignore, 'value'):
                _ignore.value = set()

            if not _ignore.value:
                # If this is the first time we are ignoring trigger execution,
                # register the pre_execute_hook
                pre_execute_hook.enter_context(
                    connection.execute_wrapper(_inject_pgtrigger_ignore)
                )

            if ignore_uri not in _ignore.value:
                try:
                    _ignore.value.add(ignore_uri)
                    yield
                finally:
                    _ignore.value.remove(ignore_uri)
            else:  # The trigger is already being ignored
                yield

        if not _ignore.value and connection.in_atomic_block:
            # We've finished all ignoring of triggers, but we are in a transaction
            # and still have a reference to the local variable. Reset it
            with connection.cursor() as cursor:
                cursor.execute('RESET pgtrigger.ignore;')


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


@contextlib.contextmanager
def ignore(*uris):
    """
    Dynamically ignore registered triggers matching URIs from executing in
    an individual thread.
    If no URIs are provided, ignore all pgtriggers from executing in an
    individual thread.

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


class Protect(Trigger):
    """A trigger that raises an exception."""

    when = Before

    def get_func(self, model):
        return f'''
            RAISE EXCEPTION
                'pgtrigger: Cannot {str(self.operation).lower()} rows from % table',
                TG_TABLE_NAME;
        '''


class FSM(Trigger):
    """Enforces a finite state machine on a field.

    Supply the trigger with the "field" that transitions and then
    a list of tuples of valid transitions to the "transitions" argument.

    .. note::

        Only non-null ``CharField`` fields are currently supported.
    """

    when = Before
    operation = Update
    field = None
    transitions = None

    def __init__(self, *, name=None, condition=None, field=None, transitions=None):
        self.field = field or self.field
        self.transitions = transitions or self.transitions

        if not self.field:  # pragma: no cover
            raise ValueError('Must provide "field" for FSM')

        if not self.transitions:  # pragma: no cover
            raise ValueError('Must provide "transitions" for FSM')

        super().__init__(name=name, condition=condition)

    def get_declare(self, model):
        return [('_is_valid_transition', 'BOOLEAN')]

    def get_func(self, model):
        col = model._meta.get_field(self.field).column
        transition_uris = '{' + ','.join([f'{old}:{new}' for old, new in self.transitions]) + '}'

        return f'''
            SELECT CONCAT(OLD.{_quote(col)}, ':', NEW.{_quote(col)}) = ANY('{transition_uris}'::text[])
                INTO _is_valid_transition;

            IF (_is_valid_transition IS FALSE AND OLD.{_quote(col)} IS DISTINCT FROM NEW.{_quote(col)}) THEN
                RAISE EXCEPTION
                    'pgtrigger: Invalid transition of field "{self.field}" from "%" to "%" on table %',
                    OLD.{_quote(col)},
                    NEW.{_quote(col)},
                    TG_TABLE_NAME;
            ELSE
                RETURN NEW;
            END IF;
        '''  # noqa


class SoftDelete(Trigger):
    """Sets a field to a value when a delete happens.

    Supply the trigger with the "field" that will be set
    upon deletion and the "value" to which it should be set.
    The "value" defaults to ``False``.

    .. note::

        This trigger currently only supports nullable ``BooleanField``,
        ``CharField``, and ``IntField`` fields.
    """

    when = Before
    operation = Delete
    field = None
    value = False

    def __init__(self, *, name=None, condition=None, field=None, value=_unset):
        self.field = field or self.field
        self.value = value if value is not _unset else self.value

        if not self.field:  # pragma: no cover
            raise ValueError('Must provide "field" for soft delete')

        super().__init__(name=name, condition=condition)

    def get_func(self, model):
        soft_field = model._meta.get_field(self.field).column
        pk_col = model._meta.pk.column

        def _render_value():
            if self.value is None:
                return 'NULL'
            elif isinstance(self.value, str):
                return f"'{self.value}'"
            else:
                return str(self.value)

        return f'''
            UPDATE {_quote(model._meta.db_table)}
            SET {soft_field} = {_render_value()}
            WHERE {_quote(pk_col)} = OLD.{_quote(pk_col)};
            RETURN NULL;
        '''

import contextlib
import copy
import hashlib
import inspect
import re

from django.db import DEFAULT_DB_ALIAS, models, router, transaction
from django.db.models.expressions import Col
from django.db.models.fields.related import RelatedField
from django.db.models.sql import Query
from django.db.models.sql.datastructures import BaseTable
from django.db.utils import ProgrammingError
import psycopg2.extensions

from pgtrigger import features
from pgtrigger import registry
from pgtrigger import utils


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
UNALLOWED = 'UNALLOWED'


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
        path = path.replace("pgtrigger.contrib", "pgtrigger")
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
        columns = ', '.join(f'{utils.quote(col)}' for col in self.columns)
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
        return f'{self.row_alias}.{utils.quote(self.col_name)}'

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
        query = _OldNewQuery(model)
        sql, args = self.resolve_expression(query).as_sql(
            compiler=query.get_compiler('default'),
            connection=utils.connection(),
        )
        sql = sql.replace('"OLD"', 'OLD').replace('"NEW"', 'NEW')
        args = tuple(psycopg2.extensions.adapt(arg).getquoted().decode() for arg in args)

        return sql % args


# Allows Trigger methods to be used as context managers, mostly for
# testing purposes
@contextlib.contextmanager
def _cleanup_on_exit(cleanup):
    yield
    cleanup()


def _ignore_func_name():
    ignore_func = "_pgtrigger_should_ignore"
    if features.schema():  # pragma: no branch
        ignore_func = f"{utils.quote(features.schema())}.{ignore_func}"

    return ignore_func


def _render_ignore_func():
    """
    Triggers can be ignored dynamically by help of a special function that's installed.
    The definition of this function is here.

    Note: This function is global and shared by all triggers in the current
    implementation. It isn't uninstalled when triggers are uninstalled.
    """
    return f'''
        CREATE OR REPLACE FUNCTION {_ignore_func_name()}(
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
                    SELECT trigger_name = ANY(_pgtrigger_ignore)
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
    timing = None

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
        timing=None,
    ):
        self.name = name or self.name
        self.level = level or self.level
        self.when = when or self.when
        self.operation = operation or self.operation
        self.condition = condition or self.condition
        self.referencing = referencing or self.referencing
        self.func = func or self.func
        self.declare = declare or self.declare
        self.timing = timing or self.timing

        if not self.level or not isinstance(self.level, Level):
            raise ValueError(f'Invalid "level" attribute: {self.level}')

        if not self.when or not isinstance(self.when, When):
            raise ValueError(f'Invalid "when" attribute: {self.when}')

        if not self.operation or not isinstance(self.operation, Operation):
            raise ValueError(f'Invalid "operation" attribute: {self.operation}')

        if self.timing and not isinstance(self.timing, Timing):
            raise ValueError(f'Invalid "timing" attribute: {self.timing}')

        if self.level == Row and self.referencing:
            raise ValueError('Row-level triggers cannot have a "referencing" attribute')

        if self.timing and self.level != Row:
            raise ValueError('Deferrable triggers must have "level" attribute as "pgtrigger.Row"')

        if self.timing and self.when != After:
            raise ValueError('Deferrable triggers must have "when" attribute as "pgtrigger.After"')

        if not self.name:
            raise ValueError('Trigger must have "name" attribute')

        self.validate_name()

    def __str__(self):
        return self.name

    def validate_name(self):
        """Verifies the name is under the maximum length"""
        if len(self.name) > MAX_NAME_LENGTH:
            raise ValueError(f'Trigger name "{self.name}" > {MAX_NAME_LENGTH} characters.')

        if not re.match(r'^[a-zA-Z0-9-_]+$', self.name):
            raise ValueError(
                f'Trigger name "{self.name}" has invalid characters.'
                ' Only alphanumeric characters, hyphens, and underscores are allowed.'
            )

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
        return f'''
            IF ({_ignore_func_name()}(TG_NAME) IS TRUE) THEN
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

    def render_trigger(self, model, function=None):
        """Renders the trigger declaration SQL statement

        Args:
            model (``models.Model``): The Django model over which
                the trigger will run.
            function (str, default=None): The function that will
                be called by the trigger. Defaults to the function that's
                automatically created for the trigger.
        """
        table = model._meta.db_table
        pgid = self.get_pgid(model)
        function = function or f"{pgid}()"

        constraint = 'CONSTRAINT' if self.timing else ''
        timing = f'DEFERRABLE INITIALLY {self.timing}' if self.timing else ''

        # Note: Postgres 14 has CREATE OR REPLACE syntax that
        # we might consider using.
        return f'''
            DROP TRIGGER IF EXISTS {pgid} on {utils.quote(table)};
            CREATE {constraint} TRIGGER {pgid}
                {self.when} {self.operation} ON {utils.quote(table)}
                {timing}
                {self.referencing or ''}
                FOR EACH {self.level} {self.render_condition(model)}
                EXECUTE PROCEDURE {function};
        '''

    def render_comment(self, model):
        """Renders the trigger commment SQL statement

        pgtrigger comments the hash of the trigger in order for us to
        determine if the trigger definition has changed
        """
        pgid = self.get_pgid(model)
        hash = self.get_hash(model)
        table = model._meta.db_table
        return f"COMMENT ON TRIGGER {pgid} ON {utils.quote(table)} IS '{hash}'"

    def render_install(self, model):
        ignore_func = _render_ignore_func()
        rendered_func = self.render_func(model)
        rendered_trigger = self.render_trigger(model)
        rendered_comment = self.render_comment(model)

        return f"{ignore_func}; {rendered_func}; {rendered_trigger}; {rendered_comment};"

    def render_uninstall(self, model):
        return utils.render_uninstall(model._meta.db_table, self.get_pgid(model))

    def allow_migrate(self, model, database=None):
        """True if the trigger for this model can be migrated.

        Defaults to using the router's allow_migrate
        """
        model = model._meta.concrete_model
        return utils.is_postgres(database) and router.allow_migrate(
            database or DEFAULT_DB_ALIAS, model._meta.app_label, model_name=model._meta.model_name
        )

    def exec_sql(self, sql, model, database=None, fetchall=False):
        """Conditionally execute SQL if migrations are allowed"""
        if self.allow_migrate(model, database=database):
            return utils.exec_sql(sql, database=database, fetchall=fetchall)

    def get_installation_status(self, model, database=None):
        """Returns the installation status of a trigger.

        The return type is (status, enabled), where status is one of:

        1. ``INSTALLED``: If the trigger is installed
        2. ``UNINSTALLED``: If the trigger is not installed
        3. ``OUTDATED``: If the trigger is installed but has been modified
        4. ``IGNORED``: If migrations are not allowed

        "enabled" is True if the trigger is installed and enabled or false
        if installed and disabled (or uninstalled).
        """
        if not self.allow_migrate(model, database=database):
            return (UNALLOWED, None)

        trigger_exists_sql = f'''
            SELECT oid, obj_description(oid) AS hash, tgenabled AS enabled
            FROM pg_trigger
            WHERE tgname='{self.get_pgid(model)}'
                AND tgrelid='{utils.quote(model._meta.db_table)}'::regclass;
        '''
        try:
            with transaction.atomic(using=database):
                results = self.exec_sql(
                    trigger_exists_sql, model, database=database, fetchall=True
                )
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

    def register(self, *models):
        """Register model classes with the trigger"""
        for model in models:
            registry.set(self.get_uri(model), model=model, trigger=self)

        return _cleanup_on_exit(lambda: self.unregister(*models))

    def unregister(self, *models):
        """Unregister model classes with the trigger"""
        for model in models:
            registry.delete(self.get_uri(model))

        return _cleanup_on_exit(lambda: self.register(*models))

    def install(self, model, database=None):
        """Installs the trigger for a model"""
        install_sql = self.render_install(model)
        with transaction.atomic(using=database):
            self.exec_sql(install_sql, model, database=database)
        return _cleanup_on_exit(lambda: self.uninstall(model, database=database))

    def uninstall(self, model, database=None):
        """Uninstalls the trigger for a model"""
        uninstall_sql = self.render_uninstall(model)
        self.exec_sql(uninstall_sql, model, database=database)
        return _cleanup_on_exit(  # pragma: no branch
            lambda: self.install(model, database=database)
        )

    def enable(self, model, database=None):
        """Enables the trigger for a model"""
        enable_sql = (
            f'ALTER TABLE {utils.quote(model._meta.db_table)}'
            f' ENABLE TRIGGER {self.get_pgid(model)};'
        )
        self.exec_sql(enable_sql, model, database=database)
        return _cleanup_on_exit(  # pragma: no branch
            lambda: self.disable(model, database=database)
        )

    def disable(self, model, database=None):
        """Disables the trigger for a model"""
        disable_sql = (
            f'ALTER TABLE {utils.quote(model._meta.db_table)}'
            f' DISABLE TRIGGER {self.get_pgid(model)};'
        )
        self.exec_sql(disable_sql, model, database=database)
        return _cleanup_on_exit(lambda: self.enable(model, database=database))  # pragma: no branch

import contextlib
import copy
import hashlib
import logging

from django.db import connection
from django.db import models
from django.db.models.expressions import Col
from django.db.models.fields.related import RelatedField
from django.db.models.sql import Query
from django.db.models.sql.datastructures import BaseTable


LOGGER = logging.getLogger('pgtrigger')


# All registered triggers for each model
registry = set()


def register(*triggers):
    """
    Register the given triggers with wrapped Model class
    """

    def _model_wrapper(model_class):
        for trigger in triggers:
            trigger.register(model_class)

        return model_class

    return _model_wrapper


class _When:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name


#: For specifying "BEFORE" in the "when" clause of a trigger
Before = _When('BEFORE')

#: For specifying "AFTER" in the "when" clause of a trigger
After = _When('AFTER')


class _Operation:
    def __init__(self, name):
        self.name = name

    def __or__(self, other):
        return _Operations(self, other)

    def __str__(self):
        return self.name


class _Operations(_Operation):
    def __init__(self, *operations):
        self.operations = operations

    def __str__(self):
        return ' OR '.join(str(operation) for operation in self.operations)


#: For specifying "UPDATE" in the "operation" clause of a trigger
Update = _Operation('UPDATE')

#: For specifying "DELETE" in the "operation" clause of a trigger
Delete = _Operation('DELETE')

#: For specifying "TRUNCATE" in the "operation" clause of a trigger
Truncate = _Operation('TRUNCATE')

#: For specifying "INSERT" in the "operation" clause of a trigger
Insert = _Operation('INSERT')


class UpdateOf(_Operation):
    """For specifying "UPDATE OF" in the "operation" clause of a trigger"""

    def __init__(self, *columns):
        if not columns:
            raise ValueError('Must provide at least one column')

        self.columns = ', '.join(f'"{col}"' for col in columns)

    def __str__(self):
        return f'UPDATE OF {self.columns}'


class Condition:
    """For specifying free-form SQL in the "condition" clause of a trigger"""

    sql = None

    def __init__(self, sql=None):
        self.sql = sql or self.sql

        if not self.sql:
            raise ValueError('Must provide SQL to condition')

    def __str__(self):
        return self.sql

    def resolve(self, model):
        return self.sql


class _OldNewQuery(Query):
    """
    A special Query object for referencing the OLD and NEW variables in a
    trigger. Only used by the Q object
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
        if filter_expr[0].startswith('old__'):
            alias = 'OLD'
        elif filter_expr[0].startswith('new__'):
            alias = 'NEW'
        else:  # pragma: no cover
            raise ValueError(
                'Filter expression on trigger.Q object must reference'
                ' old__ or new__'
            )

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
    Similar to Django's F object, allows referencing the old and new
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

    @property
    def resolved_name(self):
        return f'{self.row_alias}."{self.col_name}"'

    def resolve_expression(self, query=None, *args, **kwargs):
        return Col(
            alias=self.row_alias,
            target=query.model._meta.get_field(self.col_name),
        )


@models.fields.Field.register_lookup
class IsDistinctFrom(models.Lookup):
    """
    A custom IS DISTINCT FROM field lookup for common trigger conditions
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
    A custom IS NOT DISTINCT FROM field lookup for common trigger conditions
    """

    lookup_name = 'ndf'

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        return '%s IS NOT DISTINCT FROM %s' % (lhs, rhs), params


class Q(models.Q, Condition):
    """
    Similar to Django's Q object, allows referencing the old and new
    rows in a trigger condition.
    """

    def resolve(self, model):
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


def _drop_trigger(table, trigger_name):
    with connection.cursor() as cursor:
        cursor.execute(f'DROP TRIGGER IF EXISTS {trigger_name} ON {table};')


# Allows Trigger methods to be used as context managers, mostly for
# testing purposes
@contextlib.contextmanager
def _cleanup_on_exit(cleanup):
    yield
    cleanup()


class Trigger:
    """
    For specifying a free-form PL/pgSQL trigger function or for
    creating derived trigger classes.
    """

    when = None
    operation = None
    condition = None
    func = None

    def __init__(
        self, *, when=None, operation=None, condition=None, func=None
    ):
        self.when = when or self.when
        self.operation = operation or self.operation
        self.condition = condition or self.condition
        self.func = func or self.func

        if not self.when or not isinstance(self.when, _When):
            raise ValueError(f'Invalid "when" attribute: {self.when}')

        if not self.operation or not isinstance(self.operation, _Operation):
            raise ValueError(
                f'Invalid "operation" attribute: {self.operation}'
            )

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash(self.name)

    def get_key(self):
        """The unique key for the trigger when installing"""
        return list(self.__dict__.values())

    @property
    def name(self):
        hash = hashlib.sha1(
            ''.join(str(k) for k in self.get_key()).encode()
        ).hexdigest()[:16]
        return f'pgtrigger_{self.__class__.__name__.lower()}_'[:55] + str(hash)

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
        return []

    def get_func(self, model):
        """
        Returns the trigger function that comes between the BEGIN and END
        clause
        """
        if not self.func:
            raise ValueError(
                'Must define func attribute or implement' ' get_func'
            )
        return self.func

    def register(self, *model_classes):
        """Register model classes with the trigger"""
        for model_class in model_classes:
            registry.add((model_class, self))

        return _cleanup_on_exit(lambda: self.unregister(*model_classes))

    def unregister(self, *model_classes):
        """Unregister model classes with the trigger"""
        for model_class in model_classes:
            registry.remove((model_class, self))

        return _cleanup_on_exit(lambda: self.register(*model_classes))

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

    def render_func(self, model):
        """Renders the trigger function SQL statement"""
        return f'''
            CREATE OR REPLACE FUNCTION {self.name}()
            RETURNS TRIGGER AS $$
                {self.render_declare(model)}
                BEGIN
                    {self.get_func(model)}
                END;
            $$ LANGUAGE plpgsql;
        '''

    def render_trigger(self, model):
        """Renders the trigger declaration SQL statement"""
        table = model._meta.db_table
        return f'''
            DO $$ BEGIN
                CREATE TRIGGER {self.name}
                    {self.when} {self.operation} ON {table}
                    FOR EACH ROW {self.render_condition(model)} EXECUTE PROCEDURE {self.name}();
            EXCEPTION
                -- Ignore issues if the trigger already exists
                WHEN others THEN null;
            END $$;
        '''

    def install(self, model):
        """Installs the trigger for a model"""

        rendered_func = self.render_func(model)
        rendered_trigger = self.render_trigger(model)

        with connection.cursor() as cursor:
            cursor.execute(rendered_func)
            cursor.execute(rendered_trigger)

        return _cleanup_on_exit(lambda: self.uninstall(model))

    def uninstall(self, model):
        """Uninstalls the trigger for a model"""
        _drop_trigger(model._meta.db_table, self.name)

        return _cleanup_on_exit(  # pragma: no branch
            lambda: self.install(model)
        )

    def enable(self, model):
        """Enables the trigger for a model"""
        with connection.cursor() as cursor:
            cursor.execute(
                f'ALTER TABLE {model._meta.db_table} ENABLE TRIGGER {self.name};'
            )

        return _cleanup_on_exit(  # pragma: no branch
            lambda: self.disable(model)
        )

    def disable(self, model):
        """Disables the trigger for a model"""
        with connection.cursor() as cursor:
            cursor.execute(
                f'ALTER TABLE {model._meta.db_table} DISABLE TRIGGER {self.name};'
            )

        return _cleanup_on_exit(  # pragma: no branch
            lambda: self.enable(model)
        )


class Protect(Trigger):
    """A trigger that raises an exception"""

    when = Before

    def get_func(self, model):
        return f'''
            RAISE EXCEPTION
                'pgtrigger: Cannot {str(self.operation).lower()} rows from % table',
                TG_TABLE_NAME;
        '''


class SoftDelete(Trigger):
    """Sets a field to "False" when a delete happens"""

    when = Before
    operation = Delete
    field = None

    def __init__(self, *, condition=None, field=None):
        self.field = field or self.field

        if not self.field:  # pragma: no cover
            raise ValueError('Must provide "field" for soft delete')

        super().__init__(condition=condition)

    def get_func(self, model):
        soft_field = model._meta.get_field(self.field).column
        pk_col = model._meta.pk.column
        return f'''
            UPDATE {model._meta.db_table}
            SET {soft_field} = false
            WHERE "{pk_col}" = OLD."{pk_col}";
            RETURN NULL;
        '''


def get():
    """
    Get all triggers registered to models

    Note: Triggers can also be added to models with the pgtrigger.config
    decorator
    """
    return registry


def install():
    """
    Install all triggers registered to models
    """
    for model, trigger in get():
        LOGGER.info(
            f'pgtrigger: Installing "{trigger}" trigger for {model._meta.db_table} table.'
        )
        trigger.install(model)

    prune()


def prune():
    """
    Remove any pgtrigger triggers in the database that are not used by models.
    I.e. if a model or trigger definition is deleted from a model, ensure
    it is removed from the database
    """
    installed = {
        (model._meta.db_table, trigger.name) for model, trigger in get()
    }

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT event_object_table as table_name, trigger_name'
            '    FROM information_schema.triggers'
            '    WHERE trigger_name LIKE \'pgtrigger_%\''
        )
        triggers = set(cursor.fetchall())

    for trigger in triggers:
        if trigger not in installed:
            LOGGER.info(
                f'pgtrigger: Pruning trigger {trigger[1]}'
                f' from table {trigger[0]}...'
            )
            _drop_trigger(*trigger)


def enable():
    """
    Enables all registered triggers
    """
    for model, trigger in get():
        LOGGER.info(
            f'pgtrigger: Enabling "{trigger}" trigger for {model._meta.db_table} table.'
        )
        trigger.enable(model)


def uninstall():
    """
    Uninstalls all registered triggers.

    Running migrations will re-install any existing triggers. This
    behavior is overridable with ``settings.PGTRIGGER_INSTALL_ON_MIGRATE``

    Note: This will not uninstall triggers when deleting a model.
    This operation is performed by the "prune" command.
    """
    for model, trigger in get():
        LOGGER.info(
            f'pgtrigger: Uninstalling "{trigger}" trigger for {model._meta.db_table} table.'
        )
        trigger.uninstall(model)

    prune()


def disable():
    """
    Disables all registered triggers
    """
    for model, trigger in get():
        LOGGER.info(
            f'pgtrigger: Disabling "{trigger}" trigger for {model._meta.db_table} table.'
        )
        trigger.disable(model)

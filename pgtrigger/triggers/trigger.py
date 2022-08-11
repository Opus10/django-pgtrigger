import contextlib
import hashlib

from django.db.utils import ProgrammingError

from pgtrigger import After, Level, Operation, Row, Timing, When
from pgtrigger.core import (
    _cleanup_on_exit,
    _get_connection,
    _ignore,
    _inject_pgtrigger_ignore,
    _quote,
    _render_ignore_func,
    _render_uninstall,
    _Serializable,
    INSTALLED,
    MAX_NAME_LENGTH,
    OUTDATED,
    UNINSTALLED,
)
import pgtrigger.features
import pgtrigger.registry


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
            DROP TRIGGER IF EXISTS {pgid} on {_quote(table)};
            CREATE {constraint} TRIGGER {pgid}
                {self.when} {self.operation} ON {_quote(table)}
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
        connection = _get_connection(model)

        with contextlib.ExitStack() as pre_execute_hook:

            # Create the table name / trigger name URI to pass down to the
            # trigger.
            ignore_uri = f'{model._meta.db_table}:{self.get_pgid(model)}'

            if not hasattr(_ignore, 'value'):
                _ignore.value = {}

            if _inject_pgtrigger_ignore not in connection.execute_wrappers:
                # If this is the first time we are ignoring trigger execution,
                # register the pre_execute_hook
                pre_execute_hook.enter_context(
                    connection.execute_wrapper(_inject_pgtrigger_ignore)
                )

            if ignore_uri not in _ignore.value:
                try:
                    _ignore.value[ignore_uri] = connection
                    yield
                finally:
                    del _ignore.value[ignore_uri]
            else:  # The trigger is already being ignored
                yield

        if not any(c == connection for c in _ignore.value.values()) and connection.in_atomic_block:
            # We've finished ignoring of triggers for the connection, but we are in a transaction
            # and still have a reference to the local variable. Reset it
            with connection.cursor() as cursor:
                cursor.execute('RESET pgtrigger.ignore;')

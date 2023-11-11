import contextlib
import re
import typing
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterator,
    List,
    Sequence,
    Set,
    Tuple,
    Type,
    Union,
)

import django.db.backends.postgresql.schema as postgresql_schema
from django.apps import apps
from django.db import models, transaction
from django.db.migrations import autodetector
from django.db.migrations.operations.base import Operation
from django.db.migrations.operations.fields import AddField
from django.db.migrations.operations.models import CreateModel, IndexOperation
from django.db.migrations.state import ModelState, ProjectState

from pgtrigger import compiler, utils

PostgresSchemaEditor = postgresql_schema.DatabaseSchemaEditor


def _add_trigger(
    schema_editor: PostgresSchemaEditor,
    model: Type[models.Model],
    trigger: compiler.Trigger | Any,
) -> None:
    """Add a trigger to a model."""
    if not isinstance(trigger, compiler.Trigger):  # pragma: no cover
        trigger = trigger.compile(model)

    with transaction.atomic(using=schema_editor.connection.alias):
        # Trigger install SQL returns interpolated SQL which makes
        # params=None a necessity to avoid escaping attempts on execution.
        schema_editor.execute(trigger.install_sql, params=None)


def _remove_trigger(
    schema_editor: PostgresSchemaEditor,
    model: Type[models.Model],
    trigger: compiler.Trigger | Any,
) -> None:
    """Remove a trigger from a model."""
    if not isinstance(trigger, compiler.Trigger):  # pragma: no cover
        trigger = trigger.compile(model)

    # Trigger uninstall SQL returns interpolated SQL which makes
    # params=None a necessity to avoid escaping attempts on execution.
    schema_editor.execute(trigger.uninstall_sql, params=None)


if TYPE_CHECKING:
    TriggerOperationBase = Operation
else:
    TriggerOperationBase = object


class TriggerOperationMixin(TriggerOperationBase):
    def allow_migrate_model_trigger(
        self, schema_editor: PostgresSchemaEditor, model: Type[models.Model]
    ) -> bool:
        """
        The check for determinig if a trigger is migrated
        """
        return schema_editor.connection.vendor == "postgresql" and self.allow_migrate_model(
            schema_editor.connection.alias, model._meta.concrete_model
        )


class AddTrigger(TriggerOperationMixin, IndexOperation):
    option_name = "triggers"

    def __init__(self, model_name: str, trigger: compiler.Trigger) -> None:
        self.model_name = model_name
        self.trigger = trigger

    def state_forwards(self, app_label: str, state: ProjectState) -> None:
        model_state = state.models[app_label, self.model_name]
        model_state.options["triggers"] = model_state.options.get("triggers", []) + [self.trigger]
        state.reload_model(app_label, self.model_name, delay=True)

    def database_forwards(
        self,
        app_label: str,
        schema_editor: PostgresSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ):
        model = to_state.apps.get_model(app_label, self.model_name)
        if self.allow_migrate_model_trigger(schema_editor, model):  # pragma: no branch
            _add_trigger(schema_editor, model, self.trigger)

    def database_backwards(
        self,
        app_label: str,
        schema_editor: PostgresSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ):
        model = to_state.apps.get_model(app_label, self.model_name)
        if self.allow_migrate_model_trigger(schema_editor, model):  # pragma: no branch
            _remove_trigger(schema_editor, model, self.trigger)

    def describe(self):
        return f"Create trigger {self.trigger.name} on model {self.model_name}"

    def deconstruct(self) -> Tuple[str, List[Any], Dict[str, Union[str, compiler.Trigger]]]:
        return (
            self.__class__.__name__,
            [],
            {
                "model_name": self.model_name,
                "trigger": self.trigger,
            },
        )

    @property
    def migration_name_fragment(self) -> str:
        return f"{self.model_name_lower}_{self.trigger.name.lower()}"


def _get_trigger_by_name(model_state: ModelState, name: str) -> compiler.Trigger:
    for trigger in model_state.options.get("triggers", []):  # pragma: no branch
        trigger = typing.cast(compiler.Trigger, trigger)
        if trigger.name == name:
            return trigger

    raise ValueError(f"No trigger named {name} on model {model_state.name}")  # pragma: no cover


class RemoveTrigger(TriggerOperationMixin, IndexOperation):
    option_name = "triggers"

    def __init__(self, model_name: str, name: str) -> None:
        self.model_name = model_name
        self.name = name

    def state_forwards(self, app_label: str, state: ProjectState) -> None:
        model_state = state.models[app_label, self.model_name]
        objs = model_state.options.get("triggers", [])
        model_state.options["triggers"] = [obj for obj in objs if obj.name != self.name]
        state.reload_model(app_label, self.model_name, delay=True)

    def database_forwards(
        self,
        app_label: str,
        schema_editor: PostgresSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ):
        model = to_state.apps.get_model(app_label, self.model_name)
        if self.allow_migrate_model_trigger(schema_editor, model):  # pragma: no branch
            from_model_state = from_state.models[app_label, self.model_name_lower]
            trigger = _get_trigger_by_name(from_model_state, self.name)
            _remove_trigger(schema_editor, model, trigger)

    def database_backwards(
        self,
        app_label: str,
        schema_editor: PostgresSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ):
        model = to_state.apps.get_model(app_label, self.model_name)
        if self.allow_migrate_model_trigger(schema_editor, model):  # pragma: no branch
            to_model_state = to_state.models[app_label, self.model_name_lower]
            trigger = _get_trigger_by_name(to_model_state, self.name)
            _add_trigger(schema_editor, model, trigger)

    def describe(self) -> str:
        return f"Remove trigger {self.name} from model {self.model_name}"

    def deconstruct(self) -> Tuple[str, List[Any], Dict[str, str]]:
        return (
            self.__class__.__name__,
            [],
            {
                "model_name": self.model_name,
                "name": self.name,
            },
        )

    @property
    def migration_name_fragment(self) -> str:
        return f"remove_{self.model_name_lower}_{self.name.lower()}"


def _inject_m2m_dependency_in_proxy(proxy_op: CreateModel):
    """
    Django does not properly add dependencies to m2m fields that are base classes for
    proxy models. Inject the dependency here
    """
    for base in typing.cast(Sequence[str], proxy_op.bases):
        model = apps.get_model(base)
        creator = typing.cast(models.Model, model._meta.auto_created)
        if creator:
            for field in creator._meta.many_to_many:
                if field.remote_field.through == model:  # type: ignore - not present in stubs
                    app_label, model_name = creator._meta.label_lower.split(".")
                    proxy_op._auto_deps.append((app_label, model_name, field.name, True))  # type: ignore  - not present in stubs


if TYPE_CHECKING:
    MigrationAutodetectorBase = autodetector.MigrationAutodetector
else:
    MigrationAutodetectorBase = object


class MigrationAutodetectorMixin(MigrationAutodetectorBase):
    """A mixin that can be subclassed with MigrationAutodetector and detects triggers"""

    altered_triggers: Dict[Tuple[str, str], Dict[str, List[compiler.Trigger]]]
    kept_model_keys: Set[Tuple[str, str]]
    kept_proxy_keys: Set[Tuple[str, str]]
    new_model_keys: Set[Tuple[str, str]]
    old_model_keys: Set[Tuple[str, str]]
    new_proxy_keys: Set[Tuple[str, str]]
    old_proxy_keys: Set[Tuple[str, str]]
    generated_operations: Dict[str, List[Operation]]

    def _detect_changes(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        self.altered_triggers = {}
        return super()._detect_changes(*args, **kwargs)  # type: ignore - not present in stubs

    def _get_add_trigger_op(
        self, model: Type[models.Model], trigger: compiler.Trigger | Any
    ) -> AddTrigger:
        if not isinstance(trigger, compiler.Trigger):
            trigger = trigger.compile(model)

        model_name = typing.cast(str, model._meta.model_name)
        return AddTrigger(model_name=model_name, trigger=trigger)

    def create_altered_constraints(self) -> None:
        """
        Piggyback off of constraint generation hooks to generate
        trigger migration operations
        """
        for app_label, model_name in sorted(self.kept_model_keys | self.kept_proxy_keys):
            old_model_name = self.renamed_models.get((app_label, model_name), model_name)
            old_model_state = self.from_state.models[app_label, old_model_name]
            new_model_state = self.to_state.models[app_label, model_name]
            new_model = self.to_state.apps.get_model(app_label, model_name)

            old_triggers = old_model_state.options.get("triggers", [])
            new_triggers = [
                trigger.compile(new_model)
                for trigger in new_model_state.options.get("triggers", [])
            ]
            add_triggers = [c for c in new_triggers if c not in old_triggers]
            rem_triggers = [c for c in old_triggers if c not in new_triggers]

            self.altered_triggers.update(
                {
                    (app_label, model_name): {
                        "added_triggers": add_triggers,
                        "removed_triggers": rem_triggers,
                    }
                }
            )

        return super().create_altered_constraints()  # type: ignore - not present in stubs

    def generate_added_constraints(self) -> None:
        for (app_label, model_name), alt_triggers in self.altered_triggers.items():
            model = self.to_state.apps.get_model(app_label, model_name)
            for trigger in alt_triggers["added_triggers"]:
                self.add_operation(
                    app_label, self._get_add_trigger_op(model=model, trigger=trigger)
                )

        return super().generate_added_constraints()  # type: ignore - not present in stubs

    def generate_removed_constraints(self) -> None:
        for (app_label, model_name), alt_triggers in self.altered_triggers.items():
            for trigger in alt_triggers["removed_triggers"]:
                self.add_operation(
                    app_label, RemoveTrigger(model_name=model_name, name=trigger.name)
                )

        return super().generate_removed_constraints()  # type: ignore

    def generate_created_models(self) -> None:
        super().generate_created_models()

        added_models = self.new_model_keys - self.old_model_keys
        added_models = sorted(added_models, key=self.swappable_first_key, reverse=True)

        for app_label, model_name in added_models:
            model = self.to_state.apps.get_model(app_label, model_name)
            model_state = self.to_state.models[app_label, model_name]

            if not model_state.options.get("managed", True):
                continue  # pragma: no cover

            related_fields = {
                op.name: op.field
                for op in self.generated_operations.get(app_label, [])
                if isinstance(op, AddField) and model_name == op.model_name
            }

            related_dependencies: List[Tuple[str, str, str | None, Union[bool, str]]] = [
                (app_label, model_name, name, True) for name in sorted(related_fields)
            ]
            # Depend on the model being created
            related_dependencies.append((app_label, model_name, None, True))

            for trigger in model_state.options.pop("triggers", []):
                self.add_operation(
                    app_label,
                    self._get_add_trigger_op(model=model, trigger=trigger),
                    dependencies=related_dependencies,
                )

    def generate_created_proxies(self) -> None:
        super().generate_created_proxies()

        added = self.new_proxy_keys - self.old_proxy_keys
        for app_label, model_name in sorted(added):
            # Django has a bug that prevents it from injecting a dependency
            # to an M2M through model when a proxy model inherits it.
            # Inject an additional dependency for created proxies to
            # avoid this
            for op in self.generated_operations.get(app_label, []):
                if isinstance(op, CreateModel) and op.options.get(  # pragma: no branch
                    "proxy", False
                ):
                    _inject_m2m_dependency_in_proxy(op)

            model = self.to_state.apps.get_model(app_label, model_name)
            model_state = self.to_state.models[app_label, model_name]
            assert model_state.options.get("proxy")

            for trigger in model_state.options.pop("triggers", []):
                self.add_operation(
                    app_label,
                    self._get_add_trigger_op(model=model, trigger=trigger),
                    dependencies=[(app_label, model_name, None, True)],
                )

    def generate_deleted_proxies(self) -> None:
        deleted = self.old_proxy_keys - self.new_proxy_keys
        for app_label, model_name in sorted(deleted):
            model_state = self.from_state.models[app_label, model_name]
            assert model_state.options.get("proxy")

            for trigger in model_state.options.pop("triggers", []):
                self.add_operation(
                    app_label,
                    RemoveTrigger(model_name=model_name, name=trigger.name),
                    dependencies=[(app_label, model_name, None, True)],
                )

        super().generate_deleted_proxies()


if TYPE_CHECKING:
    SchemaEditorBase = postgresql_schema.DatabaseSchemaEditor
else:
    SchemaEditorBase = object


class DatabaseSchemaEditorMixin(SchemaEditorBase):
    """
    A schema editor mixin that can subclass a DatabaseSchemaEditor and
    handle altering column types of triggers.

    Postgres does not allow altering column types of columns used in trigger
    conditions. Here we fix this with the following approach:

    1. Detect that a column type is being changed and set a flag so that we
       can alter behavior of the schema editor.
    2. In execute(), check for the special error message that's raised
       when trying to alter a column of a trigger. Temporarily drop triggers
       during the alter statement and reinstall them. Ensure this is all
       wrapped in a transaction
    """

    temporarily_dropped_triggers: Set[Tuple[str, str]]
    is_altering_field_type: bool

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.temporarily_dropped_triggers = set()
        self.is_altering_field_type = False

    @contextlib.contextmanager
    def alter_field_type(self) -> Iterator[None]:
        """
        Temporarily sets state so that execute() knows we are trying to alter a column type
        """
        self.is_altering_field_type = True
        try:
            yield
        finally:
            self.is_altering_field_type = False

    def _alter_field(
        self,
        model: Type[models.Model],
        old_field: models.Field[Any, Any],
        new_field: models.Field[Any, Any],
        old_type: Any,
        new_type: Any,
        old_db_params: Dict[str, Any],
        new_db_params: Dict[str, Any],
        strict: bool = False,
    ) -> None:
        """
        Detects that a field type is being altered and sets the appropriate state
        """
        context = self.alter_field_type() if old_type != new_type else contextlib.nullcontext()

        with context:
            return super()._alter_field(  # type: ignore - not present in stubs
                model,
                old_field,
                new_field,
                old_type,
                new_type,
                old_db_params,
                new_db_params,
                strict=strict,
            )

    @contextlib.contextmanager
    def temporarily_drop_trigger(self, trigger: str, table: str) -> Iterator[None]:
        """
        Given a table and trigger, temporarily drop the trigger and recreate it
        after the context manager yields.
        """
        self.temporarily_dropped_triggers.add((trigger, table))

        try:
            with self.atomic, self.connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT pg_get_triggerdef(oid) FROM pg_trigger
                        WHERE tgname = '{trigger}' AND tgrelid = '{table}'::regclass;
                """
                )
                trigger_create_sql = cursor.fetchall()[0][0]
                cursor.execute(f"DROP TRIGGER {trigger} on {utils.quote(table)};")

                yield

                cursor.execute(trigger_create_sql)
        finally:
            self.temporarily_dropped_triggers.remove((trigger, table))

    def execute(self, *args: Any, **kwargs: Any) -> None:
        """
        If we are altering a field type, catch the special error psycopg raises
        when a column on a trigger is altered. Temporarily drop and recreate
        triggers to ensure the alter operation is successful.
        """
        if self.is_altering_field_type:
            try:
                with self.atomic:
                    return super().execute(*args, **kwargs)
            except Exception as exc:
                match = re.search(
                    r"cannot alter type of a column used in a trigger definition\n"
                    r'DETAIL:\s+trigger (?P<trigger>\w+).+on table "?(?P<table>\w+)"?',
                    str(exc),
                )
                if match:
                    trigger = match.groupdict()["trigger"]
                    table = match.groupdict()["table"]

                    # In practice we should never receive the same error message for
                    # the same trigger/table, but check anyways to avoid infinite
                    # recursion
                    if (
                        trigger.startswith("pgtrigger_")
                        and (table, trigger) not in self.temporarily_dropped_triggers
                    ):
                        with self.temporarily_drop_trigger(trigger, table):
                            return self.execute(*args, **kwargs)

                raise  # pragma: no cover
        else:
            return super().execute(*args, **kwargs)

    def create_model(self, model: Type[models.Model]) -> None:
        """
        Create the model

        `Meta.triggers` isn't populated on the forwards `CreateTable` migration
        (as Triggers are only added to the migration state via `AddTrigger`
        operations). `Meta.triggers` may be populated when:

        - The backwards operation of a `RemoveTable` operation where there was
          still triggers defined in the model state when the table was
          removed.
        - Creating the tables of an unmigrated app when `run_syncdb` is
          supplied to the migrate command (or when running tests).
        """
        super().create_model(model)

        for trigger in getattr(model._meta, "triggers", []):
            _add_trigger(self, model, trigger)

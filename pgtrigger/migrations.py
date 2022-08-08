from django.apps import apps
from django.db.migrations import autodetector
from django.db.migrations.operations.fields import AddField
from django.db.migrations.operations.models import CreateModel, IndexOperation


def _add_trigger(schema_editor, model, trigger):
    """Add a trigger to a model."""
    sql = trigger.render_install(model)

    # Trigger.render_install returns interpolated SQL which makes
    # params=None a necessity to avoid escaping attempts on execution.
    schema_editor.execute(sql, params=None)


def _remove_trigger(schema_editor, model, trigger):
    """Remove a trigger from a model."""
    sql = trigger.render_uninstall(model)

    # Trigger.render_uninstall returns interpolated SQL which makes
    # params=None a necessity to avoid escaping attempts on execution.
    schema_editor.execute(sql, params=None)


class TriggerOperationMixin:
    def allow_migrate_model_trigger(self, schema_editor, model):
        """
        The check for determinig if a trigger is migrated
        """
        return schema_editor.connection.vendor == 'postgresql' and self.allow_migrate_model(
            schema_editor.connection.alias, model._meta.concrete_model
        )


class AddTrigger(TriggerOperationMixin, IndexOperation):
    option_name = "triggers"

    def __init__(self, model_name, trigger):
        self.model_name = model_name
        self.trigger = trigger

    def state_forwards(self, app_label, state):
        model_state = state.models[app_label, self.model_name]
        model_state.options["triggers"] = model_state.options.get("triggers", []) + [self.trigger]
        state.reload_model(app_label, self.model_name, delay=True)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        if self.allow_migrate_model_trigger(schema_editor, model):  # pragma: no branch
            _add_trigger(schema_editor, model, self.trigger)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        if self.allow_migrate_model_trigger(schema_editor, model):  # pragma: no branch
            _remove_trigger(schema_editor, model, self.trigger)

    def describe(self):
        return f"Create trigger {self.trigger.name} on model {self.model_name}"

    def deconstruct(self):
        return (
            self.__class__.__name__,
            [],
            {
                "model_name": self.model_name,
                "trigger": self.trigger,
            },
        )

    @property
    def migration_name_fragment(self):
        return f"{self.model_name_lower}_{self.trigger.name.lower()}"


def _get_trigger_by_name(model_state, name):
    for trigger in model_state.options.get("triggers", []):  # pragma: no branch
        if trigger.name == name:
            return trigger

    raise ValueError(f"No trigger named {name} on model {model_state.name}")  # pragma: no cover


class RemoveTrigger(TriggerOperationMixin, IndexOperation):
    option_name = "triggers"

    def __init__(self, model_name, name):
        self.model_name = model_name
        self.name = name

    def state_forwards(self, app_label, state):
        model_state = state.models[app_label, self.model_name]
        objs = model_state.options.get("triggers", [])
        model_state.options["triggers"] = [obj for obj in objs if obj.name != self.name]
        state.reload_model(app_label, self.model_name, delay=True)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        if self.allow_migrate_model_trigger(schema_editor, model):  # pragma: no branch
            from_model_state = from_state.models[app_label, self.model_name_lower]
            trigger = _get_trigger_by_name(from_model_state, self.name)
            _remove_trigger(schema_editor, model, trigger)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        if self.allow_migrate_model_trigger(schema_editor, model):  # pragma: no branch
            to_model_state = to_state.models[app_label, self.model_name_lower]
            trigger = _get_trigger_by_name(to_model_state, self.name)
            _add_trigger(schema_editor, model, trigger)

    def describe(self):
        return f"Remove trigger {self.name} from model {self.model_name}"

    def deconstruct(self):
        return (
            self.__class__.__name__,
            [],
            {
                "model_name": self.model_name,
                "name": self.name,
            },
        )

    @property
    def migration_name_fragment(self):
        return f"remove_{self.model_name_lower}_{self.name.lower()}"


def _inject_m2m_dependency_in_proxy(proxy_op):
    """
    Django does not properly add dependencies to m2m fields that are base classes for
    proxy models. Inject the dependency here
    """
    for base in proxy_op.bases:
        model = apps.get_model(base)
        creator = model._meta.auto_created
        if creator:
            for field in creator._meta.many_to_many:
                if field.remote_field.through == model:
                    app_label, model_name = creator._meta.label_lower.split(".")
                    proxy_op._auto_deps.append((app_label, model_name, field.name, True))


class MigrationAutodetector(autodetector.MigrationAutodetector):
    """An autodetector that detects triggers"""

    def _detect_changes(self, *args, **kwargs):
        self.altered_triggers = {}
        return super()._detect_changes(*args, **kwargs)

    def create_altered_constraints(self):
        """
        Piggyback off of constraint generation hooks to generate
        trigger migration operations
        """
        for app_label, model_name in sorted(self.kept_model_keys | self.kept_proxy_keys):
            old_model_name = self.renamed_models.get((app_label, model_name), model_name)
            old_model_state = self.from_state.models[app_label, old_model_name]
            new_model_state = self.to_state.models[app_label, model_name]

            old_triggers = old_model_state.options.get("triggers", [])
            new_triggers = new_model_state.options.get("triggers", [])
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

        return super().create_altered_constraints()

    def generate_added_constraints(self):
        for (app_label, model_name), alt_triggers in self.altered_triggers.items():
            for trigger in alt_triggers["added_triggers"]:
                self.add_operation(app_label, AddTrigger(model_name=model_name, trigger=trigger))

        return super().generate_added_constraints()

    def generate_removed_constraints(self):
        for (app_label, model_name), alt_triggers in self.altered_triggers.items():
            for trigger in alt_triggers["removed_triggers"]:
                self.add_operation(
                    app_label, RemoveTrigger(model_name=model_name, name=trigger.name)
                )

        return super().generate_removed_constraints()

    def generate_created_models(self):
        super().generate_created_models()

        added_models = self.new_model_keys - self.old_model_keys
        added_models = sorted(added_models, key=self.swappable_first_key, reverse=True)

        for app_label, model_name in added_models:
            model_state = self.to_state.models[app_label, model_name]

            if not model_state.options.get("managed", True):
                continue  # pragma: no cover

            related_fields = {
                op.name: op.field
                for op in self.generated_operations.get(app_label, [])
                if isinstance(op, AddField) and model_name == op.model_name
            }

            related_dependencies = [
                (app_label, model_name, name, True) for name in sorted(related_fields)
            ]
            # Depend on the model being created
            related_dependencies.append((app_label, model_name, None, True))

            for trigger in model_state.options.pop("triggers", []):
                self.add_operation(
                    app_label,
                    AddTrigger(model_name=model_name, trigger=trigger),
                    dependencies=related_dependencies,
                )

    def generate_created_proxies(self):
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

            model_state = self.to_state.models[app_label, model_name]
            assert model_state.options.get("proxy")

            for trigger in model_state.options.pop("triggers", []):
                self.add_operation(
                    app_label,
                    AddTrigger(model_name=model_name, trigger=trigger),
                    dependencies=[(app_label, model_name, None, True)],
                )

    def generate_deleted_proxies(self):
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

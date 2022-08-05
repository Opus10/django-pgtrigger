import django.db.migrations.operations as migration_operations


class AppLabelOperationMixin:
    """Allows migration operations to take an app label"""

    def state_forwards(self, app_label, state):
        app_label = self.app_label or app_label
        return super().state_forwards(app_label, state)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        app_label = self.app_label or app_label
        return super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        app_label = self.app_label or app_label
        return super().database_backwards(app_label, schema_editor, from_state, to_state)

    def deconstruct(self):
        path, args, kwargs = super().deconstruct()
        kwargs["app_label"] = self.app_label
        return path, args, kwargs


class AddConstraint(AppLabelOperationMixin, migration_operations.AddConstraint):
    def __init__(self, model_name, constraint, app_label=None):
        self.app_label = app_label
        super().__init__(model_name, constraint)


class RemoveConstraint(AppLabelOperationMixin, migration_operations.RemoveConstraint):
    def __init__(self, model_name, name, app_label=None):
        self.app_label = app_label
        super().__init__(model_name, name)

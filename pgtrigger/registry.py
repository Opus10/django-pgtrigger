import collections


class TriggerNameAlreadyUsed(ValueError):
    """Thrown when a trigger name is already used for a database table."""

    pass


class TriggerFunctionNameAlreadyUsed(ValueError):
    """Thrown when a trigger function name is already used."""

    pass


# All registered triggers for each model
class _Registry(collections.UserDict):
    @property
    def pg_function_names(self):
        """
        The postgres function names of all registered triggers
        """
        return {trigger.get_pgid(model) for model, trigger in self.values()}

    @property
    def by_db_table(self):
        """
        Return the registry keys by db_table, name
        """
        return {(model._meta.db_table, trigger.name): trigger for model, trigger in self.values()}

    def __setitem__(self, key, value):
        uri = key
        model, trigger = value
        assert f"{model._meta.label}:{trigger.name}" == uri

        found_trigger = self.by_db_table.get((model._meta.db_table, trigger.name))

        if not found_trigger or found_trigger != trigger:
            if found_trigger:
                raise TriggerNameAlreadyUsed(
                    f'Trigger name "{trigger.name}" already'
                    f' used for model "{model._meta.label}"'
                    f' table "{model._meta.db_table}".'
                )

            if trigger.get_pgid(model) in self.pg_function_names:
                raise TriggerFunctionNameAlreadyUsed(
                    f'Trigger "{trigger.name}" on model "{model._meta.label}"'
                    ' has Postgres function name that\'s already in use.'
                    ' Use a different name for the trigger.'
                )

        return super().__setitem__(key, value)


_registry = _Registry()


def get():
    return _registry

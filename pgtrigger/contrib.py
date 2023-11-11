"""Additional goodies"""
import functools
import operator
from typing import Any, List, NoReturn, Optional, Tuple, Type, Union

from django.db import models

from pgtrigger import core, utils

# A sentinel value to determine if a kwarg is unset
_unset = object()


class Protect(core.Trigger):
    """A trigger that raises an exception."""

    when: core.When = core.Before

    def get_func(self, model: Type[models.Model]) -> str:
        sql = f"""
            RAISE EXCEPTION
                'pgtrigger: Cannot {str(self.operation).lower()} rows from % table',
                TG_TABLE_NAME;
        """
        return self.format_sql(sql)


class ReadOnly(Protect):
    """A trigger that prevents edits to fields.

    If `fields` are provided, will protect edits to only those fields.
    If `exclude` is provided, will protect all fields except the ones
    excluded.
    If none of these arguments are provided, all fields cannot be edited.
    """

    fields: Union[List[str], None] = None
    exclude: Union[List[str], None] = None
    operation: core.Operation = core.Update

    def __init__(
        self,
        *,
        fields: Union[List[str], None] = None,
        exclude: Union[List[str], None] = None,
        **kwargs: Any,
    ):
        self.fields = fields or self.fields
        self.exclude = exclude or self.exclude

        if self.fields and self.exclude:
            raise ValueError('Must provide only one of "fields" or "exclude" to ReadOnly trigger')

        super().__init__(**kwargs)

    def get_condition(self, model: Type[models.Model]) -> core.Condition:
        if not self.fields and not self.exclude:
            return core.Condition("OLD.* IS DISTINCT FROM NEW.*")
        else:
            if self.exclude:
                # Sanity check that the exclude list contains valid fields
                for field in self.exclude:
                    model._meta.get_field(field)

                fields = [f.name for f in model._meta.fields if f.name not in self.exclude]
            elif self.fields:
                fields = [model._meta.get_field(field).name for field in self.fields]
            else:  # pragma: no cover
                raise ValueError("Must provide either fields or exclude must have been provided")

            return functools.reduce(
                operator.or_,
                [core.Q(**{f"old__{field}__df": core.F(f"new__{field}")}) for field in fields],
            )


class FSM(core.Trigger):
    """Enforces a finite state machine on a field.

    Supply the trigger with the `field` that transitions and then
    a list of tuples of valid transitions to the `transitions` argument.

    !!! note

        Only non-null `CharField` fields are currently supported.
    """

    when: core.When = core.Before
    operation: core.Operation = core.Update
    field: str = None  # type: ignore - we make sure this is set in __init__
    transitions: List[Tuple[str, str]] = None  # type: ignore - we make sure this is set in __init__

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        condition: Union[core.Condition, None] = None,
        field: Optional[str] = None,
        transitions: Optional[List[Tuple[str, str]]] = None,
    ) -> None:
        self.field = field or self.field
        self.transitions = transitions or self.transitions

        if not self.field:  # pragma: no cover
            raise ValueError('Must provide "field" for FSM')

        if not self.transitions:  # pragma: no cover
            raise ValueError('Must provide "transitions" for FSM')

        super().__init__(name=name, condition=condition)

    def get_declare(self, model: Type[models.Model]) -> List[Tuple[str, str]]:
        return [("_is_valid_transition", "BOOLEAN")]

    def get_func(self, model: Type[models.Model]) -> str:
        col = model._meta.get_field(self.field).column
        transition_uris = "{" + ",".join([f"{old}:{new}" for old, new in self.transitions]) + "}"

        sql = f"""
            SELECT CONCAT(OLD.{utils.quote(col)}, ':', NEW.{utils.quote(col)}) = ANY('{transition_uris}'::text[])
                INTO _is_valid_transition;

            IF (_is_valid_transition IS FALSE AND OLD.{utils.quote(col)} IS DISTINCT FROM NEW.{utils.quote(col)}) THEN
                RAISE EXCEPTION
                    'pgtrigger: Invalid transition of field "{self.field}" from "%" to "%" on table %',
                    OLD.{utils.quote(col)},
                    NEW.{utils.quote(col)},
                    TG_TABLE_NAME;
            ELSE
                RETURN NEW;
            END IF;
        """  # noqa
        return self.format_sql(sql)


class SoftDelete(core.Trigger):
    """Sets a field to a value when a delete happens.

    Supply the trigger with the "field" that will be set
    upon deletion and the "value" to which it should be set.
    The "value" defaults to `False`.

    !!! note

        This trigger currently only supports nullable `BooleanField`,
        `CharField`, and `IntField` fields.
    """

    when: core.When = core.Before
    operation: core.Operation = core.Delete
    field: str = None  # type: ignore  - we make sure this is set in __init__
    value: Union[bool, str, int, object, None] = False

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        condition: Optional[core.Condition] = None,
        field: Optional[str] = None,
        value: Union[bool, str, int, object, None] = _unset,
    ) -> None:
        self.field = field or self.field
        self.value = value if value is not _unset else self.value

        if not self.field:  # pragma: no cover
            raise ValueError('Must provide "field" for soft delete')

        super().__init__(name=name, condition=condition)

    def get_func(self, model: Type[models.Model]) -> str:
        soft_field = model._meta.get_field(self.field).column
        pk = model._meta.pk

        if pk is None:  # pragma: no cover - we should never get here
            raise ValueError("Cannot use SoftDelete on a model without a primary key.")

        pk_col = pk.column

        def _render_value() -> str:
            if self.value is None:
                return "NULL"
            elif isinstance(self.value, str):
                return f"'{self.value}'"
            else:
                return str(self.value)

        sql = f"""
            UPDATE {utils.quote(model._meta.db_table)}
            SET {soft_field} = {_render_value()}
            WHERE {utils.quote(pk_col)} = OLD.{utils.quote(pk_col)};
            RETURN NULL;
        """
        return self.format_sql(sql)


class UpdateSearchVector(core.Trigger):
    """Updates a `django.contrib.postgres.search.SearchVectorField` from document fields.

    Supply the trigger with the `vector_field` that will be updated with
    changes to the `document_fields`. Optionally provide a `config_name`, which
    defaults to `pg_catalog.english`.

    This trigger uses `tsvector_update_trigger` to update the vector field.
    See [the Postgres docs](https://www.postgresql.org/docs/current/textsearch-features.html#TEXTSEARCH-UPDATE-TRIGGERS)
    for more information.

    !!! note

        `UpdateSearchVector` triggers are not compatible with [pgtrigger.ignore][] since
        it references a built-in trigger. Trying to ignore this trigger results in a
        `RuntimeError`.
    """  # noqa

    when: core.When = core.Before
    vector_field: str = None  # type: ignore  - we make sure this is set in __init__
    document_fields: List[str] = None  # type: ignore  - we make sure this is set in __init__
    config_name: str = "pg_catalog.english"

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        vector_field: Optional[str] = None,
        document_fields: Optional[List[str]] = None,
        config_name: Optional[str] = None,
    ) -> None:
        self.vector_field = vector_field or self.vector_field
        self.document_fields = document_fields or self.document_fields
        self.config_name = config_name or self.config_name

        if not self.vector_field:
            raise ValueError('Must provide "vector_field" to update search vector')

        if not self.document_fields:
            raise ValueError('Must provide "document_fields" to update search vector')

        if not self.config_name:  # pragma: no cover
            raise ValueError('Must provide "config_name" to update search vector')

        if not self.document_fields:
            raise ValueError('Must provide "document_fields" to update search vector')

        super().__init__(name=name, operation=core.Insert | core.UpdateOf(*self.document_fields))

    def ignore(self, model: Type[models.Model]) -> NoReturn:
        raise RuntimeError(f"Cannot ignore {self.__class__.__name__} triggers")

    def get_func(self, model: Type[models.Model]) -> str:
        return ""

    def render_execute(self, model: Type[models.Model]) -> str:
        document_cols = [model._meta.get_field(field).column for field in self.document_fields]
        rendered_document_cols = ", ".join(utils.quote(col) for col in document_cols)
        vector_col = model._meta.get_field(self.vector_field).column
        return (
            f"tsvector_update_trigger({utils.quote(vector_col)},"
            f" {utils.quote(self.config_name)}, {rendered_document_cols})"
        )

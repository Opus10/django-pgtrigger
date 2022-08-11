from pgtrigger import Before, Delete
from pgtrigger.core import _quote, _unset
from .trigger import Trigger


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

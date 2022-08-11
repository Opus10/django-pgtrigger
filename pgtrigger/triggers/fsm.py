from pgtrigger import Before, Update
from pgtrigger.core import _quote
from .trigger import Trigger


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

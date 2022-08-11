from pgtrigger import Before
from .trigger import Trigger


class Protect(Trigger):
    """A trigger that raises an exception."""

    when = Before

    def get_func(self, model):
        return f'''
            RAISE EXCEPTION
                'pgtrigger: Cannot {str(self.operation).lower()} rows from % table',
                TG_TABLE_NAME;
        '''

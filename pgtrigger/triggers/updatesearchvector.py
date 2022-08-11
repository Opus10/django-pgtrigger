from pgtrigger import Before, Insert, UpdateOf
from pgtrigger.core import _quote
from .trigger import Trigger


class UpdateSearchVector(Trigger):
    """Updates a ``django.contrib.postgres.search.SearchVectorField`` from document fields.

    Supply the trigger with the ``vector_field`` that will be updated with
    changes to the ``document_fields``. Optionally provide a ``config_name``, which
    defaults to ``pg_catalog.english``.

    This trigger uses ``tsvector_update_trigger`` to update the vector field.
    See `the Postgres docs <https://www.postgresql.org/docs/current/textsearch-features.html#TEXTSEARCH-UPDATE-TRIGGERS>`__
    for more information.

    .. note::

        ``UpdateSearchVector`` triggers are not compatible with `pgtrigger.ignore` since
        it references a built-in trigger. Trying to ignore this trigger results in a
        `RuntimeError`.
    """  # noqa

    when = Before
    vector_field = None
    document_fields = None
    config_name = 'pg_catalog.english'

    def __init__(self, *, name=None, vector_field=None, document_fields=None, config_name=None):
        self.vector_field = vector_field or self.vector_field
        self.document_fields = document_fields or self.document_fields
        self.config_name = config_name or self.config_name

        if not self.vector_field:
            raise ValueError('Must provide "vector_field" to update search vector')

        if not self.document_fields:
            raise ValueError('Must provide "document_fields" to update search vector')

        if not self.config_name:  # pragma: no cover
            raise ValueError('Must provide "config_name" to update search vector')

        super().__init__(name=name, operation=Insert | UpdateOf(*document_fields))

    def ignore(self, model):
        raise RuntimeError(f"Cannot ignore {self.__class__.__name__} triggers")

    def render_func(self, model):
        return ''

    def render_trigger(self, model, function=None):
        document_fields = ', '.join(_quote(field) for field in self.document_fields)
        function = (
            f'tsvector_update_trigger({_quote(self.vector_field)},'
            f' {_quote(self.config_name)}, {document_fields})'
        )
        return super().render_trigger(model, function=function)

try:
    from importlib import metadata
except ImportError:
    import importlib_metadata as metadata

__version__ = metadata.version('django-pgtrigger')

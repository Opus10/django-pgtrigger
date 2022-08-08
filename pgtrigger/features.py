from django.conf import settings


def model_meta():
    """
    True if model meta support is enabled
    """
    return getattr(settings, 'PGTRIGGER_MODEL_META', True)


def migrations():
    """
    True if migrations are enabled
    """
    return model_meta() and getattr(settings, 'PGTRIGGER_MIGRATIONS', True)


def install_on_migrate():
    """
    True if triggers should be installed after migrations
    """
    return getattr(settings, 'PGTRIGGER_INSTALL_ON_MIGRATE', False)

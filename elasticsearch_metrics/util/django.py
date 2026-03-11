"""elasticsearch_metrics.util.django: conveniences working with django"""

from django.apps import apps
from django.core import exceptions

__all__ = ("find_app_label_for_type",)


def find_app_label_for_type(given_type: type) -> str:
    # look for an installed django app the given type is defined within
    _given_module_name = given_type.__module__
    _containing_app_configs = (
        _app_config
        for _app_config in apps.get_app_configs()
        if (_app_config.module is not None)
        and _given_module_name.startswith(_app_config.module.__name__)
    )
    _nearest_containing_app_config = max(
        _containing_app_configs,
        key=lambda _config: (
            len(_config.module.__name__) if (_config.module is not None) else -1
        ),
        default=None,
    )
    if _nearest_containing_app_config is None:
        raise exceptions.ImproperlyConfigured(
            f"type {given_type.__module__}.{given_type.__qualname__} "
            "doesn't declare an explicit app_label and isn't in an "
            "application in INSTALLED_APPS."
        )
    return _nearest_containing_app_config.label

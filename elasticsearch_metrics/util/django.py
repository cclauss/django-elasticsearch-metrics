"""elasticsearch_metrics.util.django: conveniences working with django"""

from django.apps import apps
from django.core import exceptions

__all__ = ("find_app_label_for_module",)


def find_app_label_for_module(module_name: str) -> str:
    _containing_app_configs = (
        _app_config
        for _app_config in apps.get_app_configs()
        if (_app_config.module is not None)
        and module_name.startswith(_app_config.module.__name__)
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
            f"module {module_name} isn't in an application in INSTALLED_APPS."
        )
    _label = _nearest_containing_app_config.label
    if not (_label and isinstance(_label, str)):
        raise exceptions.ImproperlyConfigured(
            f"no label on app config {_nearest_containing_app_config!r}"
        )
    return _label

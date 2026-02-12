from collections.abc import Iterator
import importlib

from django.apps import AppConfig
from django.conf import settings
from django.utils.module_loading import autodiscover_modules

from elasticsearch_metrics.registry import timeseries_type_registry

_IMPCONFIG_SETTINGS_KEY = "DJELMETRICS_TIMESERIES_IMPS"


class ElasticsearchMetricsConfig(AppConfig):
    name = "elasticsearch_metrics"

    def ready(self) -> None:
        for _imp_name, _imp_module_path, _imp_config in each_timeseries_imp_config():
            timeseries_type_registry.register_imp(
                _imp_name, _imp_module_path, _imp_config
            )
        autodiscover_modules("metrics")


def each_timeseries_imp_config() -> Iterator[tuple[str, str, dict[str, str]]]:
    for _imp_name in getattr(settings, _IMPCONFIG_SETTINGS_KEY, ()):
        (_imp_module_path, _imp_config) = get_timeseries_imp_config(_imp_name)
        yield (_imp_name, _imp_module_path, _imp_config)


def get_timeseries_imp_config(imp_name: str) -> tuple[str, dict[str, str]]:
    try:
        _imp_module_path, _imp_config = getattr(settings, _IMPCONFIG_SETTINGS_KEY)
    except AttributeError as _error:
        raise ValueError(f"no `settings.{_IMPCONFIG_SETTINGS_KEY}` found") from _error
    assert isinstance(_imp_module_path, str)
    assert isinstance(_imp_config, dict)
    assert all(
        isinstance(_k, str) and isinstance(_v, str)
        for _k, _v in _imp_config.items()
    )
    return (_imp_module_path, _imp_config)

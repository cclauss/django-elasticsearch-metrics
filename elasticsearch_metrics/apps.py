import collections

from django.apps import AppConfig
from django.conf import settings
from django.utils.module_loading import autodiscover_modules

from elasticsearch_metrics.registry import djelme_registry

_IMPS_KEY = "DJELMETRICS_TIMESERIES_IMPS"


class ElasticsearchMetricsConfig(AppConfig):
    name = "elasticsearch_metrics"

    def ready(self) -> None:
        for (
            _imp_name,
            _imp_module_path,
            _imp_kwargs,
        ) in _each_timeseries_settings_entry():
            djelme_registry.register_imp(
                _imp_name, _imp_module_path, _imp_kwargs
            )
        autodiscover_modules("metrics")
        djelme_registry.on_app_ready()


###
# accessing django settings


def _each_timeseries_settings_entry() -> (
    collections.abc.Iterator[tuple[str, str, dict[str, str]]]
):
    for _imp_name, _imp_settings in getattr(settings, _IMPS_KEY, {}).items():
        for _imp_module_path, _imp_kwargs in _imp_settings.items():
            # TODO: better errors
            assert isinstance(_imp_module_path, str)
            assert isinstance(_imp_kwargs, dict)
            assert all(
                isinstance(_k, str) and isinstance(_v, str)
                for _k, _v in _imp_kwargs.items()
            )
            yield (_imp_name, _imp_module_path, _imp_kwargs)

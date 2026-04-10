import collections

from django.apps import AppConfig
from django.utils.module_loading import autodiscover_modules

from elasticsearch_metrics.registry import djelme_registry


class ElasticsearchMetricsConfig(AppConfig):
    name = "elasticsearch_metrics"

    def ready(self) -> None:
        # discover any `foo.metrics` in installed apps
        autodiscover_modules("metrics")
        # call `djelme_when_ready` once for each djelme imp module used by a backend
        _backends_by_imp: dict[str, list[str]] = collections.defaultdict(list)
        for _backend_name, _imp_name, _ in djelme_registry.each_backend_settings():
            _backends_by_imp[_imp_name].append(_backend_name)
        for _imp_module_name, _backend_names in _backends_by_imp.items():
            _imp_module = djelme_registry.get_imp_module(_imp_module_name)
            _imp_module.djelme_when_ready(
                backends=[
                    djelme_registry.get_backend(_name) for _name in _backend_names
                ]
            )

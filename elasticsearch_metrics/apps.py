import collections

from django.apps import AppConfig
from django.conf import settings
from django.utils.module_loading import autodiscover_modules

from elasticsearch_metrics.registry import djelme_registry

AUTOSETUP_SETTING = "DJELME_AUTOSETUP"


class ElasticsearchMetricsConfig(AppConfig):
    name = "elasticsearch_metrics"

    def ready(self) -> None:
        # load backends settings
        _backend_names_by_module = collections.defaultdict(list)
        for (
            _backend_name,
            _imp_module_name,
            _,
        ) in djelme_registry.each_backend_settings():
            _backend_names_by_module[_imp_module_name].append(_backend_name)
        # discover any `foo.metrics` in installed apps
        autodiscover_modules("metrics")
        # call `djelme_when_ready` for each imp module (only once)
        for _imp_module_name, _backend_names in _backend_names_by_module.items():
            _imp_module = djelme_registry.get_imp_module(_imp_module_name)
            _imp_module.djelme_when_ready(
                backends=[
                    djelme_registry.get_backend(_name) for _name in _backend_names
                ]
            )
        # autosetup? (default no)
        if getattr(settings, AUTOSETUP_SETTING, False) is True:
            _types_by_backend = djelme_registry.recordtypes_by_backend()
            for _backend_name, _recordtypes in _types_by_backend.items():
                djelme_registry.get_backend(_backend_name).djelme_setup(_recordtypes)

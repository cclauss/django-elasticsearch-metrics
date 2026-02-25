import collections

from django.apps import AppConfig
from django.conf import settings
from django.utils.module_loading import autodiscover_modules

from elasticsearch_metrics.registry import djelme_registry

IMPS_SETTING = "DJELMETRICS_TIMESERIES_IMPS"
AUTOSYNC_SETTING = "DJELMETRICS_AUTOSYNC"


class ElasticsearchMetricsConfig(AppConfig):
    name = "elasticsearch_metrics"

    def ready(self) -> None:
        # load imps settings
        _imp_names_by_module = collections.defaultdict(list)
        for _imp_name, _imp_module_path, _imp_kwargs in _each_imp_setting():
            _imp_names_by_module[_imp_module_path].append(_imp_name)
            djelme_registry.register_imp(_imp_name, _imp_module_path, _imp_kwargs)
        # discover any `foo.metrics` in installed apps
        autodiscover_modules("metrics")
        # call `djelme_when_ready` on each imp module
        for _imp_module_path, _imp_names in _imp_names_by_module.items():
            _imp_module = djelme_registry.get_imp_module(_imp_module_path)
            _imp_module.djelme_when_ready(
                imps=[djelme_registry.get_imp(_name) for _name in _imp_names]
            )
        # autosync
        if getattr(settings, AUTOSYNC_SETTING, False):
            for _imp in djelme_registry.each_imp():
                for _recordtype in djelme_registry.each_recordtype(imp_name=_imp.imp_name):
                    _recordtype.setup_timeseries_indexes()

###
# accessing django settings


def _each_imp_setting() -> collections.abc.Iterator[tuple[str, str, dict[str, str]]]:
    for _imp_name, _imp_settings in getattr(settings, IMPS_SETTING, {}).items():
        for _imp_module_path, _imp_kwargs in _imp_settings.items():
            # TODO: better errors
            assert isinstance(_imp_module_path, str)
            assert isinstance(_imp_kwargs, dict)
            assert all(
                isinstance(_k, str) and isinstance(_v, str)
                for _k, _v in _imp_kwargs.items()
            )
            yield (_imp_name, _imp_module_path, _imp_kwargs)

import collections

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import autodiscover_modules

from elasticsearch_metrics.registry import djelme_registry

BACKENDS_SETTING = "DJELME_BACKENDS"
AUTOSETUP_SETTING = "DJELME_AUTOSETUP"


class ElasticsearchMetricsConfig(AppConfig):
    name = "elasticsearch_metrics"

    def ready(self) -> None:
        # load backends settings
        _backend_names_by_module = collections.defaultdict(list)
        for _backend_name, _imp_module_path, _imp_kwargs in _each_backend_setting():
            _backend_names_by_module[_imp_module_path].append(_backend_name)
            djelme_registry.register_backend(
                _backend_name, _imp_module_path, _imp_kwargs
            )
        # discover any `foo.metrics` in installed apps
        autodiscover_modules("metrics")
        # call `djelme_when_ready` on each imp module
        for _imp_module_path, _backend_names in _backend_names_by_module.items():
            _imp_module = djelme_registry.get_imp_module(_imp_module_path)
            _imp_module.djelme_when_ready(
                backends=[
                    djelme_registry.get_backend(_name) for _name in _backend_names
                ]
            )
        # autosetup? (default no)
        if getattr(settings, AUTOSETUP_SETTING, False) is True:
            for _backend in djelme_registry.each_backend():
                _backend.setup_timeseries_indexes()


###
# accessing django settings


def _each_backend_setting() -> (
    collections.abc.Iterator[tuple[str, str, dict[str, str]]]
):
    for _backend_name, _backend_imps in getattr(settings, BACKENDS_SETTING, {}).items():
        if len(_backend_imps) > 1:
            raise ImproperlyConfigured(
                BACKENDS_SETTING, "only one imp per backend, at the moment"
            )
        for _imp_module_path, _imp_kwargs in _backend_imps.items():
            if not (
                isinstance(_imp_module_path, str)
                and isinstance(_imp_kwargs, dict)
                and all(
                    isinstance(_k, str) and isinstance(_v, str)
                    for _k, _v in _imp_kwargs.items()
                )
            ):
                raise ImproperlyConfigured(
                    BACKENDS_SETTING,
                    'expected {"mybackend": {"imp.path": {"imp_config": "..."}}}',
                )
            yield (_backend_name, _imp_module_path, _imp_kwargs)

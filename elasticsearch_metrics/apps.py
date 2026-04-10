import collections

from django.apps import AppConfig
from django.conf import settings
from django.core import checks
from django.db.models.signals import post_migrate
from django.utils.module_loading import autodiscover_modules

from elasticsearch_metrics.registry import djelme_registry

AUTOSETUP_SETTING = "DJELME_AUTOSETUP"


def do_djelme_setup(*, app_config, stdout, **kwargs):
    _types_by_backend = djelme_registry.recordtypes_by_backend(app_label=app_config.label)
    breakpoint()
    for _backend_name, _recordtypes in _types_by_backend.items():
        _backend = djelme_registry.get_backend(_backend_name)
        _backend.djelme_setup(_recordtypes)


def check_djelme_setup(app_configs, **kwargs):
    _errors = []
    for _app_config in app_configs:
        for _recordtype in djelme_registry.each_recordtype(app_label=_app_config.label):
            if not _recordtype.check_djelme_setup():
                _errors.append(
                    checks.Error(
                        "elasticsearch_metrics requires setup!",
                        hint="run `manage.py djelme_backend_setup`",
                        obj=_recordtype,
                        id="elasticsearch_metrics.E001",
                    )
                )
    return _errors


class ElasticsearchMetricsConfig(AppConfig):
    name = "elasticsearch_metrics"

    def ready(self) -> None:
        # register django system checks
        checks.register(check_djelme_setup)
        # connect django signals
        if getattr(settings, AUTOSETUP_SETTING, False) is True:
            post_migrate.connect(do_djelme_setup)
        # discover any `foo.metrics` in installed apps
        autodiscover_modules("metrics")
        # load backends settings
        _backend_names_by_module = collections.defaultdict(list)
        for (
            _backend_name,
            _imp_module_name,
            _,
        ) in djelme_registry.each_backend_settings():
            _backend_names_by_module[_imp_module_name].append(_backend_name)
        # call `djelme_when_ready` once for each imp module
        for _imp_module_name, _backend_names in _backend_names_by_module.items():
            _imp_module = djelme_registry.get_imp_module(_imp_module_name)
            _imp_module.djelme_when_ready(
                backends=[
                    djelme_registry.get_backend(_name) for _name in _backend_names
                ]
            )

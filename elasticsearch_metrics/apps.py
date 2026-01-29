from django.apps import AppConfig
from django.conf import settings
from django.utils.module_loading import autodiscover_modules


class ElasticsearchMetricsConfig(AppConfig):
    name = "elasticsearch_metrics"

    def ready(self):
        for _name, _config in settings.DJELME_CONNECTIONS:
            ...  # connections.add_connection(_name, ...)
        autodiscover_modules("metrics")

from django.apps import AppConfig
from django.conf import settings
from django.utils.module_loading import autodiscover_modules


class ElasticsearchMetricsConfig(AppConfig):
    name = "elasticsearch_metrics"

    def ready(self):
        for _djelme_connection in each_djelmetrics_connection():
            _djelme_connection
            ...  # connections.add_connection(_name, ...)
        autodiscover_modules("metrics")

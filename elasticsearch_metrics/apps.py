from django.apps import AppConfig
from django.utils.module_loading import autodiscover_modules


class ElasticsearchMetricsConfig(AppConfig):
    name = "elasticsearch_metrics"

    def ready(self):
        autodiscover_modules("metrics")

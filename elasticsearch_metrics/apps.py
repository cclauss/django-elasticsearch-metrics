from django.apps import AppConfig
from django.utils.module_loading import autodiscover_modules

from elasticsearch_metrics.djelmetrics_imps import each_djelmetrics_imp


class ElasticsearchMetricsConfig(AppConfig):
    name = "elasticsearch_metrics"

    def ready(self):
        for _imp in each_djelmetrics_imp():
            _imp.configure()
        autodiscover_modules("metrics")

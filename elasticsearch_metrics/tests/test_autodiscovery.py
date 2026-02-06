from django.test import SimpleTestCase

from elasticsearch_metrics.registry import registry


class TestShowMetricsCommand(SimpleTestCase):
    def test_app_metrics_are_automatically_registered(self):
        # dummy6app.Dummy6Metric should already be registered because it's
        # in metrics.py
        assert registry.get_metric("dummy6app.Dummy6Metric")

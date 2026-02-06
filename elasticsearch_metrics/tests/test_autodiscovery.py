from django.test import TestCase

from elasticsearch_metrics.registry import registry


class TestShowMetricsCommand(TestCase):
    def test_app_metrics_are_automatically_registered(self):
        # dummyapp.DummyMetric should already be registered because it's
        # in metrics.py
        assert registry.get_metric("dummyapp.DummyMetric")

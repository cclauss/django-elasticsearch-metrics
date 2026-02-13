from elasticsearch_metrics.registry import registry
from elasticsearch_metrics.tests._test_util import SimpleDjelmeTestCase


class TestShowMetricsCommand(SimpleDjelmeTestCase):
    def test_app_metrics_are_automatically_registered(self):
        # dummy6app.Dummy6Metric should already be registered because it's
        # in metrics.py
        assert registry.get_recordtype("dummy6app.Dummy6Metric")

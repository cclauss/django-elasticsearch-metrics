from elasticsearch_metrics.registry import registry
from elasticsearch_metrics.tests._test_util import SimpleDjelmeTestCase


class TestAutodiscovery(SimpleDjelmeTestCase):
    def test_app_metrics_are_automatically_registered(self):
        # from dummy6app/metrics.py:
        self.assertTrue(registry.get_recordtype("dummy6app.Dummy6Metric"))
        # from dummy8app/metrics.py:
        self.assertTrue(registry.get_recordtype("dummy8app.Dummy8Event"))
        self.assertTrue(registry.get_recordtype("dummy8app.Dummy8Event"))

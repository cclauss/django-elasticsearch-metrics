from elasticsearch_metrics.management.commands import show_metrics
from elasticsearch_metrics.tests._test_util import SimpleDjelmeTestCase


class TestShowMetricsCommand(SimpleDjelmeTestCase):
    def test_without_args_by_name(self):
        out, err = self.run_mgmt_command(show_metrics.Command())
        assert "Dummy6Metric" in out
        assert "dummy6app_dummy6metric_*" in out

    def test_without_args_by_command(self):
        out, err = self.run_mgmt_command("show_metrics")
        assert "Dummy6Metric" in out
        assert "dummy6app_dummy6metric_*" in out

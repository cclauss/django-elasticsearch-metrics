from django.test import TestCase

from elasticsearch_metrics.management.commands import show_metrics
from elasticsearch_metrics.tests._test_util import run_mgmt_command


class TestShowMetricsCommand(TestCase):
    def test_without_args_by_name(self):
        out, err = run_mgmt_command(show_metrics.Command())
        assert "Dummy6Metric" in out
        assert "dummy6app_dummy6metric_*" in out

    def test_without_args_by_command(self):
        out, err = run_mgmt_command('show_metrics')
        assert "Dummy6Metric" in out
        assert "dummy6app_dummy6metric_*" in out

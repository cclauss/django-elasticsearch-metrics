from unittest import mock, skip

from django.test import SimpleTestCase

from elasticsearch_metrics.management.commands import sync_metrics
from elasticsearch_metrics.imps import elastic6
from elasticsearch_metrics.registry import registry
from elasticsearch_metrics.tests._test_util import run_mgmt_command


class TestSyncMetrics(SimpleTestCase):
    def setUp(self):
        self.mock_sync_index_template = self.enterContext(
            mock.patch(
                "elasticsearch_metrics.imps.elastic6.Metric.sync_index_template"
            ),
        )

    def test_without_args(self):
        out, err = run_mgmt_command(sync_metrics.Command)
        assert self.mock_sync_index_template.call_count == len(
            list(registry.get_metrics())
        )
        assert "Synchronized metrics." in out

    def test_with_invalid_app(self):
        out, err = run_mgmt_command(sync_metrics.Command, "notanapp")
        assert "No metrics found for app 'notanapp'" in err

    def test_with_app_label(self):
        class DummyMetric2(elastic6.Metric):
            class Meta:
                app_label = "dummyapp2"

        out, err = run_mgmt_command(sync_metrics.Command, "dummyapp2")
        assert self.mock_sync_index_template.call_count == 1

    @skip("TODO: connection selection")
    def test_with_connection(self):
        self.settings.DJELMETRICS_IMPS = {
            "default": {"hosts": "localhost:9201"},
            "alternate": {"hosts": "localhost:9202"},
        }
        out, err = run_mgmt_command(sync_metrics.Command, "--connection", "alternate")
        call_kwargs = self.mock_sync_index_template.call_args[1]
        assert call_kwargs["using"] == "alternate"
        assert "Using connection: 'alternate'" in out

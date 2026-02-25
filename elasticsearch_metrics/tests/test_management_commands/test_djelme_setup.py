from unittest import mock, skip

from elasticsearch_metrics.management.commands import djelme_setup
from elasticsearch_metrics.imps import elastic6
from elasticsearch_metrics.registry import registry
from elasticsearch_metrics.tests._test_util import SimpleDjelmeTestCase


class TestDjelmeSetup(SimpleDjelmeTestCase):
    def setUp(self):
        self.mock6_sync_index_template = self.enterContext(
            mock.patch(
                "elasticsearch_metrics.imps.elastic6.Metric.sync_index_template"
            ),
        )
        self.mock8_sync_index_template = self.enterContext(
            mock.patch(
                "elasticsearch_metrics.imps.elastic8.TimeseriesRecord.sync_index_template"
            ),
        )

    def test_without_args(self):
        out, err = self.run_mgmt_command(djelme_setup.Command)
        _call_count = (
            self.mock6_sync_index_template.call_count
            + self.mock8_sync_index_template.call_count
        )
        assert _call_count == len(list(registry.each_recordtype()))
        assert "Synchronized recordtypes." in out

    def test_with_invalid_app(self):
        out, err = self.run_mgmt_command(djelme_setup.Command, "notanapp")
        assert "No recordtypes found for app 'notanapp'" in err

    def test_with_app_label(self):
        class DummyMetric2(elastic6.Metric):
            class Meta:
                app_label = "dummyapp2"

        out, err = self.run_mgmt_command(djelme_setup.Command, "dummyapp2")
        assert self.mock_sync_index_template.call_count == 1

    @skip("TODO: connection selection")
    def test_with_connection(self):
        self.settings.DJELMETRICS_TIMESERIES_IMPS = {
            "default": [
                "elasticsearch_metrics.imps.elastic6",
                {"hosts": "localhost:9201"},
            ],
            "alternate": [
                "elasticsearch_metrics.imps.elastic8",
                {"hosts": "localhost:9202"},
            ],
        }
        out, err = self.run_mgmt_command(
            djelme_setup.Command, "--connection", "alternate"
        )
        call_kwargs = self.mock_sync_index_template.call_args[1]
        assert call_kwargs["using"] == "alternate"
        assert "Using connection: 'alternate'" in out

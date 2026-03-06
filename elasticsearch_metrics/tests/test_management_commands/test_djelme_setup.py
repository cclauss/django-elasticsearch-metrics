from unittest import mock

from elasticsearch_metrics.management.commands import djelme_backend_setup
from elasticsearch_metrics.imps import elastic6
from elasticsearch_metrics.registry import djelme_registry
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
        out, err = self.run_mgmt_command(djelme_backend_setup)
        _call_count = (
            self.mock6_sync_index_template.call_count
            + self.mock8_sync_index_template.call_count
        )
        assert _call_count == len(list(djelme_registry.each_recordtype()))
        assert "Synchronized recordtypes." in out

    def test_with_invalid_app(self):
        out, err = self.run_mgmt_command(djelme_backend_setup, "notanapp")
        assert "No recordtypes found for app 'notanapp'" in err

    def test_with_app_label(self):
        class DummyMetric2(elastic6.Metric):
            class Meta:
                app_label = "dummyapp2"

        out, err = self.run_mgmt_command(djelme_backend_setup, "dummyapp2")
        _call_count = (
            self.mock6_sync_index_template.call_count
            + self.mock8_sync_index_template.call_count
        )
        assert _call_count == 1

    def test_with_connection(self):
        with self.settings(
            DJELME_BACKENDS={
                "my_old_elastic": {
                    "elasticsearch_metrics.imps.elastic6": {"hosts": "localhost:9206"},
                },
                "my_lessold_elastic": {
                    "elasticsearch_metrics.imps.elastic8": {"hosts": "localhost:9208"},
                },
            }
        ):
            _out1, _err1 = self.run_mgmt_command(
                djelme_backend_setup, "--backend", "my_old_elastic"
            )
            _out2, _err2 = self.run_mgmt_command(
                djelme_backend_setup, "--backend", "my_lessold_elastic"
            )
        _call1_kwargs = self.mock8_sync_index_template.call_args[1]
        assert _call1_kwargs["using"] == "my_old_elastic"
        assert "Using connection: 'my_old_elastic'" in _out1

        _call2_kwargs = self.mock8_sync_index_template.call_args[2]
        assert _call2_kwargs["using"] == "my_lessold_elastic"
        assert "Using connection: 'my_lessold_elastic'" in _out2

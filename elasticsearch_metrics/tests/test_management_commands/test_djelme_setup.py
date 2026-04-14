import unittest

from django.core.management import CommandError

from elasticsearch_metrics.management.commands import djelme_backend_setup
from elasticsearch_metrics.imps import elastic6
from elasticsearch_metrics.registry import djelme_registry
from elasticsearch_metrics.tests.util import SimpleDjelmeTestCase


class TestDjelmeSetup(SimpleDjelmeTestCase):
    mock6_sync_index_template: unittest.mock.Mock
    mock8_sync_index_template: unittest.mock.Mock

    def setUp(self):
        self.mock6_sync_index_template = self.enterContext(
            unittest.mock.patch(
                "elasticsearch_metrics.imps.elastic6.Metric.sync_index_template"
            ),
        )
        self.mock8_sync_index_template = self.enterContext(
            unittest.mock.patch(
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
        with self.assertRaises(CommandError) as _raises:
            self.run_mgmt_command(djelme_backend_setup, "notanapp")
        assert "No recordtypes found for app 'notanapp'" in str(_raises.exception)

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

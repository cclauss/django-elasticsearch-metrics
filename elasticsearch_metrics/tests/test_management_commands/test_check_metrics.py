from unittest import mock

from elasticsearch_metrics import exceptions
from elasticsearch_metrics.management.commands import check_metrics
from elasticsearch_metrics.registry import registry
from elasticsearch_metrics.tests._test_util import SimpleDjelmeTestCase


class TestCheckMetrics(SimpleDjelmeTestCase):
    def setUp(self):
        self.mock6_check_index_template = self.enterContext(
            mock.patch(
                "elasticsearch_metrics.imps.elastic6.Metric.check_index_template"
            ),
        )
        self.mock8_check_index_template = self.enterContext(
            mock.patch(
                "elasticsearch_metrics.imps.elastic8.TimeseriesRecord.check_index_template"
            ),
        )

    def test_exits_with_error_if_out_of_sync_6(self):
        self.mock6_check_index_template.side_effect = (
            exceptions.IndexTemplateNotFoundError(
                "Index template does not exist", client_error=None
            )
        )
        with self.assertRaises(SystemExit):
            self.run_mgmt_command(check_metrics.Command)

    def test_exits_with_error_if_out_of_sync_8(self):
        self.mock8_check_index_template.side_effect = (
            exceptions.IndexTemplateNotFoundError(
                "Index template does not exist", client_error=None
            )
        )
        with self.assertRaises(SystemExit):
            self.run_mgmt_command(check_metrics.Command)

    def test_exits_with_success(self):
        self.mock6_check_index_template.return_value = True
        self.mock8_check_index_template.return_value = True
        self.run_mgmt_command(check_metrics.Command)
        _call_count = (
            self.mock6_check_index_template.call_count
            + self.mock8_check_index_template.call_count
        )
        assert _call_count == len(list(registry.each_recordtype()))

from unittest import mock

from django.test import SimpleTestCase

from elasticsearch_metrics import exceptions
from elasticsearch_metrics.management.commands import check_metrics
from elasticsearch_metrics.registry import registry
from elasticsearch_metrics.tests._test_util import run_mgmt_command


class TestCheckMetrics(SimpleTestCase):
    def setUp(self):
        self.mock_check_index_template = self.enterContext(
            mock.patch(
                "elasticsearch_metrics.imps.elastic6.Metric.check_index_template"
            ),
        )

    def test_exits_with_error_if_out_of_sync(self):
        self.mock_check_index_template.side_effect = (
            exceptions.IndexTemplateNotFoundError(
                "Index template does not exist", client_error=None
            )
        )
        with self.assertRaises(SystemExit):
            run_mgmt_command(check_metrics.Command)

    def test_exits_with_success(self):
        self.mock_check_index_template.return_value = True
        run_mgmt_command(check_metrics.Command)
        assert self.mock_check_index_template.call_count == len(
            list(registry.get_metrics())
        )

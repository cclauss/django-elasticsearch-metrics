from elasticsearch_metrics.management.commands import show_recordtypes
from elasticsearch_metrics.tests._test_util import SimpleDjelmeTestCase


class TestShowRecordtypesCommand(SimpleDjelmeTestCase):
    def test_without_args_by_name(self):
        out, err = self.run_mgmt_command(show_recordtypes.Command())
        assert "Dummy6Metric" in out
        assert "dummy6app_dummy6metric_*" in out

    def test_without_args_by_command(self):
        out, err = self.run_mgmt_command("show_recordtypes")
        assert "Dummy6Metric" in out
        assert "dummy6app_dummy6metric_*" in out

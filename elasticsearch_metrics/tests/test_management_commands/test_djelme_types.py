from elasticsearch_metrics.management.commands import djelme_backend_types
from elasticsearch_metrics.tests._test_util import SimpleDjelmeTestCase


class TestDjelmeTypesCommand(SimpleDjelmeTestCase):
    def test_without_args_by_name(self):
        out, err = self.run_mgmt_command(djelme_backend_types.Command())
        assert "Dummy6Metric" in out
        assert "Dummy8Event" in out

    def test_without_args_by_command(self):
        out, err = self.run_mgmt_command("djelme_backend_types")
        assert "Dummy6Metric" in out
        assert "Dummy8Event" in out

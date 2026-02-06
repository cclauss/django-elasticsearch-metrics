import abc
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.test import SimpleTestCase

from elasticsearch_metrics.djelmetrics_db import get_djelmetrics_connection


def mock_es6_save():
    return mock.patch("elasticsearch_metrics.imps.elastic6.Document.save")


def mock_es8_save():
    return mock.patch("elasticsearch_metrics.imps.elastic8.Document.save")


def run_mgmt_command(cmd: str | BaseCommand, *args, **options) -> tuple[str, str]:
    """run a django management command, return (stdout, stderr) tuple
    """
    _out, _err = StringIO(), StringIO()
    call_command(cmd, *args, **options, stdout=_out, stderr=_err)
    return _out.getvalue(), _err.getvalue()


# base class for testing with actual elasticsearch running
class RealElasticTestCase(SimpleTestCase, abc.ABC):
    def withFreshDjelme(self, connection_name: str):
        # connection_name should be in elasticsearch_metrics.tests.settings.DJELMETRICS_CONNECTIONS
        self.djelme_connection = get_djelmetrics_connection(connection_name)
        self.djelme_connection.teardown_db()  # in case it already exists
        self.djelme_connection.setup_db()  # in case it already exists
        # TODO: patch settings/registry?
        self.addCleanup(self.djelme_connection.teardown_db)


class MockSaveTestCase(SimpleTestCase, abc.ABC):
    def setUp(self):
        self.mocked_es6_save = self.enterContext(mock_es6_save())
        self.mocked_es8_save = self.enterContext(mock_es8_save())

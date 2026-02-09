import abc
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.test import SimpleTestCase

from elasticsearch_metrics.djelmetrics_imps import each_djelmetrics_imp


def mock_es6_save():
    return mock.patch("elasticsearch_metrics.imps.elastic6.Document.save")


def run_mgmt_command(cmd: str | BaseCommand | type[BaseCommand], *args, **options) -> tuple[str, str]:
    """run a django management command, return (stdout, stderr) tuple

    may be called with a command name or Command type/instance
    """
    _cmd = (
        cmd
        if isinstance(cmd, (str, BaseCommand))
        else cmd()
    )
    _out, _err = StringIO(), StringIO()
    try:
        call_command(_cmd, *args, **options, stdout=_out, stderr=_err)
    except CommandError as _cmd_err:
        return _out.getvalue(), '\n'.join((_err.getvalue(), str(_cmd_err)))

    return _out.getvalue(), _err.getvalue()


# base class for testing with actual elasticsearch running
class RealElasticTestCase(SimpleTestCase, abc.ABC):
    def setUp(self):
        # TODO: prefix index names, avoid collisions across test runs
        # get settings from elasticsearch_metrics.tests.settings.DJELMETRICS_IMPS
        _djelme_connections = list(each_djelmetrics_imp())
        for _conn in _djelme_connections:
            _conn.teardown_db()  # in case it already exists
        for _conn in _djelme_connections:
            _conn.setup_db()
        for _conn in _djelme_connections:
            self.addCleanup(_conn.teardown_db)


class MockSaveTestCase(SimpleTestCase, abc.ABC):
    def setUp(self):
        self.mocked_es6_save = self.enterContext(mock_es6_save())

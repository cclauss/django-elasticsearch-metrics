from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.test import SimpleTestCase

from elasticsearch_metrics.timeseries_imps import each_timeseries_imp


class SimpleDjelmeTestCase(SimpleTestCase):
    """SimpleDjelmeTestCase: base test case with djelme-specific conveniences"""

    def enterContext(self, context_manager):
        # TestCase.enterContext added in python3.11 -- implementing here until 3.10 eol
        result = context_manager.__enter__()
        self.addCleanup(lambda: context_manager.__exit__(None, None, None))
        return result

    def run_mgmt_command(
        self,
        cmd: str | BaseCommand | type[BaseCommand],
        *args,
        **options,
    ) -> tuple[str, str]:
        """run a django management command, return (stdout, stderr) tuple

        may be called with a command name or Command type/instance
        """
        _cmd = cmd if isinstance(cmd, (str, BaseCommand)) else cmd()
        _out, _err = StringIO(), StringIO()
        try:
            call_command(_cmd, *args, **options, stdout=_out, stderr=_err)
        except CommandError as _cmd_err:
            return _out.getvalue(), "\n".join((_err.getvalue(), str(_cmd_err)))

        return _out.getvalue(), _err.getvalue()


class RealElasticTestCase(SimpleDjelmeTestCase):
    """RealElasticTestCase: base test case with actual elasticsearch running"""

    __auto_setup_imps: bool

    def __init_subclass__(cls, /, auto_setup_imps: bool = True, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.__auto_setup_imps = auto_setup_imps

    def setUp(self):
        super().setUp()
        if self.__auto_setup_imps:
            self.setup_djelme_imps()

    def tearDown(self):
        super().tearDown()
        self.teardown_djelme_imps()

    def setup_djelme_imps(self):
        # TODO: prefix index names, avoid collisions across test runs
        # get settings from elasticsearch_metrics.tests.settings.DJELMETRICS_TIMESERIES_IMPS
        self.teardown_djelme_imps()  # in case any already exist
        for _imp in each_timeseries_imp():
            _imp.setup_timeseries_indexes()

    def teardown_djelme_imps(self):
        for _imp in each_timeseries_imp():
            _imp.teardown_timeseries_indexes()


class MockSaveTestCase(SimpleDjelmeTestCase):
    def setUp(self):
        self.mocked_es6_save = self.enterContext(
            mock.patch("elasticsearch_metrics.imps.elastic6.Document.save"),
        )
        self.mocked_es8_save = self.enterContext(
            mock.patch("elasticsearch_metrics.imps.elastic8.Document.save"),
        )

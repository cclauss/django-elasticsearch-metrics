import contextlib
from io import StringIO
import types
import typing
from unittest import mock
import uuid

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.test import SimpleTestCase

from elasticsearch_metrics.registry import djelme_registry


class SimpleDjelmeTestCase(SimpleTestCase):
    """SimpleDjelmeTestCase: base test case with djelme-specific conveniences"""

    def setUp(self):
        super().setUp()
        clear_setup_check_caches()

    def enterContext(self, context_manager):
        # unittest.TestCase.enterContext added in python3.11 -- implementing here until 3.10 eol
        result = context_manager.__enter__()
        self.addCleanup(lambda: context_manager.__exit__(None, None, None))
        return result

    def run_mgmt_command(
        self, cmd: str | BaseCommand | types.ModuleType, *args: str, **options: str
    ) -> tuple[str, str]:
        """run a django management command, return (stdout, stderr) tuple

        wraps django.core.management.call_command to handle string-io and
        also accept a management command module
        """
        _cmd = cmd.Command() if isinstance(cmd, types.ModuleType) else cmd
        _out, _err = StringIO(), StringIO()
        call_command(_cmd, *args, **options, stdout=_out, stderr=_err)
        return _out.getvalue(), _err.getvalue()


class RealElasticTestCase(SimpleDjelmeTestCase):
    """RealElasticTestCase: base test case with actual elasticsearch running"""

    __autosetup_backends: bool
    __autoteardown_backends: bool

    def __init_subclass__(
        cls,
        /,  # kwargs on class creation e.g. `Foo(RealElasticTestCase, autosetup_djelme_backends=False)
        autosetup_djelme_backends: bool,  # required
        autoteardown_djelme_backends: bool = True,
        **kwargs: typing.Any,
    ):
        super().__init_subclass__(**kwargs)
        cls.__autosetup_backends = autosetup_djelme_backends
        cls.__autoteardown_backends = autoteardown_djelme_backends

    def setUp(self):
        self.enterContext(prefixed_index_names())
        super().setUp()
        if self.__autosetup_backends:
            setup_backends()

    def tearDown(self):
        if self.__autoteardown_backends:
            teardown_backends()
        super().tearDown()


class MockSaveTestCase(SimpleDjelmeTestCase):
    def setUp(self):
        super().setUp()
        self.mocked_es6_save = self.enterContext(
            mock.patch("elasticsearch_metrics.imps.elastic6.Document.save"),
        )
        self.mocked_es8_save = self.enterContext(
            mock.patch("elasticsearch_metrics.imps.elastic8.esdsl.Document.save"),
        )
        self.mocked_es6_require_been_setup = self.enterContext(
            mock.patch("elasticsearch_metrics.imps.elastic6.Metric.require_been_setup"),
        )
        self.mocked_es8_require_been_setup = self.enterContext(
            mock.patch(
                "elasticsearch_metrics.imps.elastic8.DjelmeRecordtype.require_been_setup"
            ),
        )


@contextlib.contextmanager
def prefixed_index_names(prefix: str = ""):
    _name_prefix = prefix or f"{uuid.uuid4().hex}_"
    with (
        mock.patch(
            "elasticsearch_metrics.imps.elastic8.TimeseriesRecord.get_timeseries_name_prefix",
            return_value=_name_prefix,
        ),
        mock.patch(
            "elasticsearch_metrics.imps.elastic6.BaseMetric.get_timeseries_name_prefix",
            return_value=_name_prefix,
        ),
    ):
        yield


def clear_setup_check_caches():
    from elasticsearch_metrics.imps import elastic6, elastic8

    elastic6.Metric.require_been_setup.cache_clear()
    elastic8.DjelmeRecordtype.require_been_setup.cache_clear()


def setup_backends():
    # backends based on settings in django.conf.settings.DJELME_BACKENDS
    _types_by_backend = djelme_registry.recordtypes_by_backend()
    for _backend_name, _recordtypes in _types_by_backend.items():
        djelme_registry.get_backend(_backend_name).djelme_setup(_recordtypes)


def teardown_backends():
    # backends based on settings in django.conf.settings.DJELME_BACKENDS
    _types_by_backend = djelme_registry.recordtypes_by_backend()
    for _backend_name, _recordtypes in _types_by_backend.items():
        djelme_registry.get_backend(_backend_name).djelme_teardown(_recordtypes)

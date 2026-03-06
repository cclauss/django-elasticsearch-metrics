from io import StringIO
from unittest import mock
import types
import typing

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.test import SimpleTestCase

from elasticsearch_metrics.registry import djelme_registry


class SimpleDjelmeTestCase(SimpleTestCase):
    """SimpleDjelmeTestCase: base test case with djelme-specific conveniences"""

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
        autosetup_djelme_backends: bool = True,
        autoteardown_djelme_backends: bool = True,
        **kwargs: typing.Any,
    ):
        super().__init_subclass__(**kwargs)
        cls.__autosetup_backends = autosetup_djelme_backends
        cls.__autoteardown_backends = autoteardown_djelme_backends

    def setUp(self):
        super().setUp()
        if self.__autosetup_backends:
            self.setup_backends()

    def tearDown(self):
        super().tearDown()
        if self.__autoteardown_backends:
            self.teardown_backends()

    def setup_backends(self):
        # TODO: prefix index names, avoid collisions across test runs
        # get settings from elasticsearch_metrics.tests.settings.DJELME_BACKENDS
        # self.teardown_backends()  # in case any already exist
        for _backend in djelme_registry.each_backend():
            _backend.djelme_setup(
                djelme_registry.each_recordtype(backend_name=_backend.backend_name)
            )

    def teardown_backends(self):
        for _backend in djelme_registry.each_backend():
            _backend.djelme_teardown(
                djelme_registry.each_recordtype(backend_name=_backend.backend_name)
            )


class MockSaveTestCase(SimpleDjelmeTestCase):
    def setUp(self):
        self.mocked_es6_save = self.enterContext(
            mock.patch("elasticsearch_metrics.imps.elastic6.Document.save"),
        )
        self.mocked_es8_save = self.enterContext(
            mock.patch("elasticsearch_metrics.imps.elastic8.Document.save"),
        )

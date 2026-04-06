import doctest
import importlib

_MODULES_WITH_DOCTESTS = (
    "elasticsearch_metrics.imps.elastic8",
    "elasticsearch_metrics.util.anon_enough",
    "elasticsearch_metrics.util.timeseries_naming",
    "elasticsearch_metrics.util.timeparts",
)


_DOCTEST_OPTIONFLAGS = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE


def load_tests(loader, tests, ignore):
    for _module_name in _MODULES_WITH_DOCTESTS:
        _module = importlib.import_module(_module_name)
        tests.addTests(doctest.DocTestSuite(_module, optionflags=_DOCTEST_OPTIONFLAGS))
    return tests

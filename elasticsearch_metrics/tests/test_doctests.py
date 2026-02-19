import doctest

import elasticsearch_metrics.util.index_name
import elasticsearch_metrics.imps.elastic8

_MODULES_WITH_DOCTESTS = (
    elasticsearch_metrics.util.index_name,
    elasticsearch_metrics.imps.elastic8,
)


_DOCTEST_OPTIONFLAGS = (
    doctest.ELLIPSIS
    | doctest.NORMALIZE_WHITESPACE
)


def load_tests(loader, tests, ignore):
    for _module in _MODULES_WITH_DOCTESTS:
        tests.addTests(doctest.DocTestSuite(_module, optionflags=_DOCTEST_OPTIONFLAGS))
    return tests

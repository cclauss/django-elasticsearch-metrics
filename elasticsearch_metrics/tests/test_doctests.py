import doctest

import elasticsearch_metrics.date_coverage

_MODULES_WITH_DOCTESTS = (
    elasticsearch_metrics.date_coverage,
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

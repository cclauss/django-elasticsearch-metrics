from __future__ import annotations
from collections.abc import Iterator
import importlib

from django.conf import settings

from elasticsearch_metrics.protocols import (
    ProtoDjelmetricsImp,
    ProtoDjelmetricsImpModule,
)

__all__ = (
    "each_djelmetrics_imp",
    "get_djelmetrics_imp",
    "ProtoDjelmetricsImp",
)


def each_djelmetrics_imp() -> Iterator[ProtoDjelmetricsImp]:
    for _imp_name in getattr(settings, "DJELMETRICS_IMPS", ()):
        yield get_djelmetrics_imp(_imp_name)


def get_djelmetrics_imp(imp_name: str) -> ProtoDjelmetricsImp:
    try:
        _raw_imp_config = settings.DJELMETRICS_IMPS[imp_name]
    except KeyError as _error:
        raise ValueError(
            f"{imp_name!r} not found in `settings.DJELMETRICS_IMPS`"
        ) from _error
    try:
        _imp_path = _raw_imp_config["DJELMETRICS_IMP"]
    except KeyError as _error:
        raise ValueError(
            f"missing 'DJELMETRICS_IMP' from {imp_name!r} in `settings.DJELMETRICS_IMPS`"
            " -- must be a path to a djelme imp module like those under"
            "`elasticsearch_metrics.imps...`"
        ) from _error
    try:
        _imp_module = importlib.import_module(_imp_path)
    except ImportError as _error:
        raise ValueError(
            f"could not import {_imp_path!r} for `settings.DJELMETRICS_IMPS[{imp_name!r}]`"
        ) from _error
    assert isinstance(_imp_module, ProtoDjelmetricsImpModule)
    _imp_config = {
        _k: _v for _k, _v in _raw_imp_config.items() if _k != "DJELMETRICS_IMP"
    }
    return _imp_module.djelme_imp_from_config(imp_name, _imp_config)

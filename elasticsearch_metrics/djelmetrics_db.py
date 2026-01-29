from __future__ import annotations
from collections.abc import Iterator
import importlib

from django.conf import settings

from elasticsearch_metrics.protocols import (
    ProtoDjelmetricsDatabase,
    ProtoDjelmetricsImp,
)


__all__ = (
    'each_djelmetrics_db',
    'get_djelmetrics_db',
    'ProtoDjelmetricsDatabase',
)


def each_djelmetrics_db() -> Iterator[ProtoDjelmetricsDatabase]:
    for _db_name in getattr(settings, 'DJELMETRICS_DATABASES', ()):
        yield get_djelmetrics_db(_db_name)


def get_djelmetrics_db(db_name: str) -> ProtoDjelmetricsDatabase:
    try:
        _db_config = settings.DJELMETRICS_DATABASES[db_name]
    except KeyError:
        raise ValueError(f'{db_name!r} not found in `settings.DJELMETRICS_DATABASES`')
    try:
        _imp_path = _db_config.pop('DJELMETRICS_IMP')
    except KeyError:
        raise ValueError(
            f"missing 'DJELMETRICS_IMP' from {db_name!r} in `settings.DJELMETRICS_DATABASES`"
            ' -- must be a path to a djelme imp module like those under'
            '`elasticsearch_metrics.djelme_imps...`'
        )
    try:
        _imp_module = importlib.import_module(_imp_path)
    except ImportError:
        raise ValueError(f'could not import {_imp_path!r} for `settings.DJELMETRICS_DATABASES[{db_name!r}]`')
    assert isinstance(_imp_module, ProtoDjelmetricsImp)
    return _imp_module.djelme_imp_from_config(_db_config)

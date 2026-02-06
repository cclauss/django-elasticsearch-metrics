from __future__ import annotations
from collections.abc import Iterator
import importlib

from django.conf import settings

from elasticsearch_metrics.protocols import (
    ProtoDjelmetricsConnection,
    ProtoDjelmetricsImp,
)


__all__ = (
    'each_djelmetrics_connection',
    'get_djelmetrics_connection',
    'ProtoDjelmetricsConnection',
)


def each_djelmetrics_connection() -> Iterator[ProtoDjelmetricsConnection]:
    for _connection_name in getattr(settings, 'DJELMETRICS_CONNECTIONS', ()):
        yield get_djelmetrics_connection(_connection_name)


def get_djelmetrics_connection(connection_name: str) -> ProtoDjelmetricsConnection:
    try:
        _connection_config = settings.DJELMETRICS_CONNECTIONS[connection_name]
    except KeyError:
        raise ValueError(f'{connection_name!r} not found in `settings.DJELMETRICS_CONNECTIONS`')
    try:
        _imp_path = _connection_config.pop('DJELMETRICS_IMP')
    except KeyError:
        raise ValueError(
            f"missing 'DJELMETRICS_IMP' from {connection_name!r} in `settings.DJELMETRICS_CONNECTIONS`"
            ' -- must be a path to a djelme imp module like those under'
            '`elasticsearch_metrics.djelme_imps...`'
        )
    try:
        _imp_module = importlib.import_module(_imp_path)
    except ImportError:
        raise ValueError(f'could not import {_imp_path!r} for `settings.DJELMETRICS_CONNECTIONS[{connection_name!r}]`')
    assert isinstance(_imp_module, ProtoDjelmetricsImp)
    return _imp_module.djelme_imp_from_config(_connection_config)

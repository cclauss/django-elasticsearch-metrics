"""elasticsearch_metrics.util.timeseries_naming

for naming timeseries indexes with lexical time coverage
(so an index-name wildcard can be used to query several indexes)
"""

from __future__ import annotations

__all__ = (
    "format_index_name",
    "parse_index_name",
    "format_index_pattern",
    "parse_index_pattern",
    "format_namepart",
    "format_template_name",
)

from collections.abc import Iterator
import datetime
import itertools

_DELIMITER: str = "_"
_TIMEPART_MIN_LEN: int = 2
_TEMPLATE_NAME_SUFFIX = "_template"


TimeseriesIndexNamePattern = tuple[str, str, tuple[int, ...]]


def format_index_name(
    prefix: str,
    recordtype: str,
    timeparts: tuple[int, ...] = (),  # empty () -- all time
) -> str:
    """get a full/specific index name, no wildcards or lists
    >>> format_index_name('aoeu', 'mynote', (9999,22))
    'aoeu_mynote_9999_22_'
    """
    _parts = [
        format_namepart(prefix),
        format_namepart(recordtype),
    ]
    if timeparts:
        _parts.append(_format_timename(*timeparts))
    _parts.append(
        ""
    )  # always end with the delimiter, to match wildcard pattern `foo_bar_123_*`
    return _DELIMITER.join(_parts)


def format_index_pattern(
    prefix: str,
    recordtype: str,
    timeparts: tuple[int, ...] = (),  # empty () -- all time
) -> str:
    """get an index-name pattern for all indexes within the given timeparts
    >>> format_index_pattern('aoeu', 'mynote', (9999,22))
    'aoeu_mynote_9999_22_*'
    """
    return f"{format_index_name(prefix, recordtype, timeparts)}*"


def format_template_name(
    prefix: str,
    recordtype: str,
) -> str:
    """
    >>> format_template_name('blah', 'fleh')
    'blah_fleh__template'
    """
    return _DELIMITER.join(
        (format_namepart(prefix), format_namepart(recordtype), _TEMPLATE_NAME_SUFFIX)
    )


def format_namepart(namepart: str) -> str:
    return namepart.replace(_DELIMITER, "").lower()


def parse_index_name(given_name: str) -> TimeseriesIndexNamePattern:
    """
    >>> parse_index_name('blah_fleh_1123_58')
    ('blah', 'fleh', (1123, 58))
    >>> parse_index_name('aoeu_mynote_2001')
    ('aoeu', 'mynote', (2001,))
    """
    _prefix, _recordtype, _timename = given_name.split(_DELIMITER, maxsplit=2)
    return (_prefix, _recordtype, tuple(_parse_timename(_timename)))


def parse_index_pattern(given_pattern: str) -> TimeseriesIndexNamePattern:
    """
    >>> parse_index_pattern('blah_fleh_1123_58')
    ('blah', 'fleh', (1123, 58))
    >>> parse_index_pattern('aoeu_mynote_2001_')
    ('aoeu', 'mynote', (2001,))
    >>> parse_index_pattern('a_b_7766_5_*')
    ('a', 'b', (7766, 5))
    >>> parse_index_pattern('a_b_7766_555_*')
    ('a', 'b', (7766, 555))
    """
    _prefix, _recordtype, _timename = given_pattern.split(_DELIMITER, maxsplit=2)
    return (_prefix, _recordtype, tuple(_parse_timename(_timename)))


def timerange_parts(start: tuple[int, ...], end: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(_each_timerange_part(start, end))


def _each_timerange_part(
    start: tuple[int, ...], end: tuple[int, ...]
) -> Iterator[int, ...]:
    for _startpart, _endpart in zip(start, end, strict=False):
        yield _startpart if (_startpart == _endpart) else None


def _format_timename(*timeparts: int) -> str:
    """
    >>> _format_timename(1999)
    '1999'
    >>> _format_timename(2345)
    '2345'

    use with any series of integers
    >>> _format_timename(1234, 5, 6, 7)
    '1234_05_06_07'
    >>> _format_timename(2345, 6, 2, 17, 4200)
    '2345_06_02_17_4200'
    >>> _format_timename(6, 1, 8, 2)
    '06_01_08_02'
    """
    return _DELIMITER.join(map(_format_timepart, timeparts))


def _parse_timename(given_timename: str) -> Iterator[int]:
    """
    >>> list(_parse_timename('7766_555_04'))
    [7766, 555, 4]
    >>> list(_parse_timename('7766_555'))
    [7766, 555]
    >>> list(_parse_timename('7766_555_'))
    [7766, 555]
    """
    for _part in given_timename.rstrip("*").rstrip(_DELIMITER).split(_DELIMITER):
        yield int(_part)


def timename_from_datestr(given_date: str, part_count: int) -> str:
    """
    >>> timename_from_datestr('2345-06-07', 1)
    '2345'
    >>> timename_from_datestr('2345-06-07T01:00:00+00:00', 2)
    '2345_06'
    >>> timename_from_datestr('2345-06-07', 3)
    '2345_06_07'
    >>> timename_from_datestr('2345-06-07', 4)
    '2345_06_07_00'
    >>> timename_from_datestr('2345-06-07', 5)
    '2345_06_07_00_00'
    >>> timename_from_datestr('2345-06-07', 6)
    '2345_06_07_00_00_00'
    >>> timename_from_datestr('2345-06-07T01:01:02+00:00', 7)
    '2345_06_07_01_01_02'
    """
    return timename_from_date(
        datetime.datetime.fromisoformat(given_date),
        part_count=part_count,
    )


def timename_from_date(given_date: datetime.date, part_count: int) -> str:
    """
    >>> timename_from_date(datetime.date(3456, 7, 8), 2)
    '3456_07'
    """
    _timeparts = itertools.islice(_each_timepart_from_date(given_date), part_count)
    return _format_timename(*_timeparts)


def timeparts_from_date(given_date: datetime.date, part_count: int) -> tuple[str, ...]:
    """
    >>> timeparts_from_date(datetime.date(3456, 7, 8), 2)
    (3456, 7)
    >>> timeparts_from_date(datetime.date(3456, 7, 8), 4)
    (3456, 7, 8, 0)
    """
    _parts = itertools.chain(_each_timepart_from_date(given_date), itertools.repeat(0))
    return tuple(itertools.islice(_parts, part_count))


def _each_timepart_from_date(given_date: datetime.date) -> Iterator[int]:
    yield given_date.year
    yield given_date.month
    yield given_date.day
    if isinstance(given_date, datetime.datetime):
        yield given_date.hour
        yield given_date.minute
        yield given_date.second


def _format_timepart(timepart: int) -> str:
    return f"{timepart:0{_TIMEPART_MIN_LEN}}"

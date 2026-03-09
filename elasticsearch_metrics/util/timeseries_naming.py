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

import collections
from collections.abc import Iterator
import datetime
import itertools

_DELIMITER: str = "_"
_TIMEPART_MIN_LEN: int = 2
_TEMPLATE_NAME_SUFFIX = "_template"
_MAX_INDEXPATTERN_COMMAS: int = 5


TimeseriesIndexNamePattern = tuple[str, str, tuple[int, ...]]


def format_index_name(
    prefix: str,
    recordtype: str,
    timeparts: collections.abc.Iterable[int] = (),  # empty () -- all time
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


def format_index_name_for_date(
    given_date: datetime.date,
    *,
    prefix: str,
    recordtype: str,
    timedepth: int,
) -> str:
    """get a full/specific index name, no wildcards or lists
    >>> format_index_name_for_date(datetime.date(9876,5,4), prefix='aoeu', recordtype='mynote', timedepth=2)
    'aoeu_mynote_9876_05_'
    """
    return format_index_name(
        prefix, recordtype, timeparts_from_date(given_date, timedepth)
    )


def format_index_pattern(
    prefix: str,
    recordtype: str,
    timeparts: collections.abc.Iterable[int] = (),  # empty () -- all time
) -> str:
    """get an index-name pattern for all indexes within the given timeparts
    >>> format_index_pattern('aoeu', 'mynote', (9999,22))
    'aoeu_mynote_9999_22_*'
    """
    return f"{format_index_name(prefix, recordtype, timeparts)}*"


# def _each_timeparts_for_timerange(
#     from_timeparts: collections.abc.Sequence[int],
#     thru_timeparts: collections.abc.Sequence[int],
#     max_timedepth: int,
# ) -> collections.abc.Generator[tuple[int, ...]]:
#     """
#     yield timeparts to cover the given timerange (in no particular order)
#
#     >>> sorted(_each_timeparts_for_timerange((1999, 2), (1999, 3), max_timedepth=1))
#     [(1999,)]
#     >>> sorted(_each_timeparts_for_timerange((1999, 2), (1999, 11)))
#     >>> sorted(_each_timeparts_for_timerange((1999, 2), (2000, 11)))
#     >>> sorted(_each_timeparts_for_timerange((1999, 2), (2002, 11)))
#     >>> sorted(_each_timeparts_for_timerange((1999,), (2002,)))
#     >>> sorted(_each_timeparts_for_timerange((1999, 27, 17, 0, 3), (1999, 27, 17, 0, 223,)))
#     >>> sorted(_each_timeparts_for_timerange((1999, 27, 17, 0, 3), (2002, 117, 17, 0, 3)))
#     """
#     for _frompart, _untilpart in itertools.islice(
#         zip(from_timeparts, thru_timeparts, strict=False),
#         max_timedepth,  # stop at max depth
#     ):
#         if _untilpart == _frompart:  # shared part
#             yield (_untilpart,)
#             for _restparts in _each_timeparts_for_timerange(
#                 from_timeparts[1:], thru_timeparts[1:], max_timedepth - 1
#             ):
#                 yield from itertools.chain([_untilpart], _restparts)
#         elif (_untilpart - _frompart) <= _MAX_INDEXPATTERN_COMMAS:  # not too far apart
#             for _commadpart in range(_frompart, _untilpart):
#                 yield from ...
#             ...
#         else:  # too far apart
#             ...


def format_index_pattern_for_timerange(
    prefix: str,
    recordtype: str,
    from_timeparts: collections.abc.Iterable[int],
    thru_timeparts: collections.abc.Iterable[int],
    max_timedepth: int,
) -> str:
    """get an index-name pattern for all indexes within a timepart range
    >>> format_index_pattern_for_timerange('aoeu', 'mynote',
    ...     (5020, 2, 2), (5020, 2, 20),
    ...     max_timedepth=2)
    'aoeu_mynote_5020_02_*'
    >>> format_index_pattern_for_timerange('aoeu', 'mynote',
    ...     (5020, 2, 2), (5020, 12, 20),
    ...     max_timedepth=2)
    'aoeu_mynote_5020_*'
    """
    return format_index_pattern(
        prefix,
        recordtype,
        _timerange_part_overlap(from_timeparts, thru_timeparts, max_timedepth),
    )


def format_index_pattern_for_daterange(
    prefix: str,
    recordtype: str,
    from_date: datetime.date,
    thru_date: datetime.date,
    max_timedepth: int,
) -> str:
    """get an index-name pattern for all indexes within a date range
    >>> format_index_pattern_for_daterange('aoeu', 'mynote',
    ...     datetime.date(2050, 5, 5), datetime.date(2050, 5, 8),
    ...     max_timedepth=2)
    'aoeu_mynote_2050_05_*'
    """
    return format_index_pattern_for_timerange(
        prefix,
        recordtype,
        _each_timepart_from_date(from_date),
        _each_timepart_from_date(thru_date),
        max_timedepth,
    )


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


def _timerange_part_overlap(
    start: collections.abc.Iterable[int],
    end: collections.abc.Iterable[int],
    max_overlap: int,
) -> collections.abc.Iterable[int]:
    return tuple(itertools.islice(_shared_timeparts(start, end), max_overlap))


def _shared_timeparts(
    start: collections.abc.Iterable[int], end: collections.abc.Iterable[int]
) -> Iterator[int]:
    for _startpart, _endpart in zip(start, end, strict=False):
        if _startpart != _endpart:
            break
        yield _startpart


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


def timeparts_from_date(given_date: datetime.date, part_count: int) -> tuple[int, ...]:
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

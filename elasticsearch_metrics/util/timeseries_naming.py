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
_DEFAULT_PATTERN_FANOUT: int = 3


TimeseriesIndexNamePattern = tuple[str, str, tuple[int, ...]]


def format_index_name(
    prefix: str,
    recordtype: str,
    timeparts: collections.abc.Sequence[int] = (),  # empty () -- all time
    max_timedepth: int | None = None,
) -> str:
    """get a full/specific index name, no wildcards or lists
    >>> format_index_name('a', 'rt', (9999, 22))
    'a_rt_9999_22_'
    >>> format_index_name('a', 'rt', (9999, 22, 0))
    'a_rt_9999_22_00_'
    """
    _parts = [
        format_namepart(prefix),
        format_namepart(recordtype),
    ]
    if timeparts:
        _trimmed_timeparts = (
            timeparts if (max_timedepth is None) else timeparts[:max_timedepth]
        )
        _parts.append(_format_timename(*_trimmed_timeparts))
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
    >>> format_index_name_for_date(datetime.date(9876,5,4), prefix='ap', recordtype='rt', timedepth=2)
    'ap_rt_9876_05_'
    """
    return format_index_name(
        prefix, recordtype, timeparts_from_date(given_date, timedepth)
    )


def format_index_pattern(
    prefix: str,
    recordtype: str,
    timeparts: collections.abc.Sequence[int] = (),  # empty () -- all time
    max_timedepth: int | None = None,
) -> str:
    """get an index-name pattern for all indexes within the given timeparts
    >>> format_index_pattern('a', 'rt', (9999,22))
    'a_rt_9999_22_*'
    >>> format_index_pattern('a', 'rt', (1, 2, 3, 4, 5))
    'a_rt_01_02_03_04_05_*'
    >>> format_index_pattern('a', 'rt', (1, 2, 3, 4, 5), max_timedepth=3)
    'a_rt_01_02_03_*'
    """
    return f"{format_index_name(prefix, recordtype, timeparts, max_timedepth)}*"


def _each_timeparts_for_timerange(
    from_timeparts: collections.abc.Sequence[int],
    until_timeparts: collections.abc.Sequence[int],
    *,
    timedepth: int,
    max_fanout: int,
    include_less_granular: bool,
) -> collections.abc.Generator[tuple[tuple[int, ...], bool]]:
    """
    yield (timeparts, is_wildcard) tuples
    """
    if timedepth <= 0:
        yield (), True  # reached timedepth; wildcard
        return
    _from_part, *_from_rest = from_timeparts
    _until_part, *_until_rest = until_timeparts
    assert _from_part <= _until_part

    if include_less_granular:
        yield (), False  # include less-granular non-wildcard index, if it exists
    if _from_part == _until_part:
        for _rest_parts, _is_wildcard in _each_timeparts_for_timerange(
            _from_rest,
            _until_rest,
            timedepth=timedepth - 1,
            max_fanout=max_fanout,
            include_less_granular=include_less_granular,
        ):
            yield (_from_part, *_rest_parts), _is_wildcard
    elif (_until_part - _from_part) <= max_fanout:  # not too far apart
        for _parallel_part in range(_from_part, _until_part):
            yield (_parallel_part,), True  # wildcard
        if any(_until_rest):  # some of the "until" bucket is included
            _from_zero = tuple(itertools.repeat(0, len(_until_rest)))
            for _rest_parts, _is_wildcard in _each_timeparts_for_timerange(
                _from_zero,
                _until_rest,
                timedepth=timedepth - 1,
                max_fanout=max_fanout,
                include_less_granular=include_less_granular,
            ):
                yield (_until_part, *_rest_parts), _is_wildcard
    else:  # too far apart
        yield (), True  # wildcard


def _each_indexpattern_for_timerange(
    prefix: str,
    recordtype: str,
    from_timeparts: collections.abc.Sequence[int],
    until_timeparts: collections.abc.Sequence[int],
    *,
    timedepth: int,
    max_fanout: int,
    include_less_granular: bool,
    only_datelike: bool,
) -> collections.abc.Generator[str]:
    for _timeparts, _is_wildcard in _each_timeparts_for_timerange(
        from_timeparts,
        until_timeparts,
        timedepth=timedepth,
        max_fanout=max_fanout,
        include_less_granular=include_less_granular,
    ):
        if only_datelike and (0 in _timeparts[1:3]):
            # intuitively, zero is a fine value for any datepart except the second and third
            continue  # skip month zero and day zero
        if _is_wildcard:
            yield format_index_pattern(prefix, recordtype, _timeparts)
        else:
            yield format_index_name(prefix, recordtype, _timeparts)


def format_index_pattern_for_timerange(
    prefix: str,
    recordtype: str,
    from_timeparts: collections.abc.Sequence[int],
    until_timeparts: collections.abc.Sequence[int],
    *,
    timedepth: int,
    max_fanout: int = _DEFAULT_PATTERN_FANOUT,
    include_less_granular: bool = False,
    only_datelike: bool = False,
) -> str:
    """get an index-name pattern for all indexes within a timepart range

    >>> format_index_pattern_for_timerange('ap', 'rt',
    ...     (5020, 2, 2), (5020, 12, 20), timedepth=2)
    'ap_rt_5020_*'
    >>> format_index_pattern_for_timerange('ap', 'rt',
    ...     (5020, 2, 2), (5020, 2, 20), timedepth=2)
    'ap_rt_5020_02_*'
    >>> format_index_pattern_for_timerange('ap', 'rt',
    ...     (5020, 2, 2), (5020, 2, 20), timedepth=2, include_less_granular=True)
    'ap_rt_,ap_rt_5020_,ap_rt_5020_02_*'
    >>> format_index_pattern_for_timerange('ap', 'rt',
    ...     (5020, 2, 1), (5020, 3), timedepth=2)
    'ap_rt_5020_02_*'
    >>> format_index_pattern_for_timerange('ap', 'rt',
    ...     (5020, 2, 2), (5020, 2, 3), timedepth=3)
    'ap_rt_5020_02_02_*'
    >>> format_index_pattern_for_timerange('ap', 'rt',
    ...     (5020, 2, 2), (5020, 3, 3), timedepth=3)
    'ap_rt_5020_02_*,ap_rt_5020_03_00_*,ap_rt_5020_03_01_*,ap_rt_5020_03_02_*'
    >>> format_index_pattern_for_timerange('ap', 'rt',
    ...     (5020, 2, 2), (5022, 3, 3), timedepth=3, only_datelike=True)
    'ap_rt_5020_*,ap_rt_5021_*,ap_rt_5022_01_*,ap_rt_5022_02_*,ap_rt_5022_03_01_*,ap_rt_5022_03_02_*'
    >>> format_index_pattern_for_timerange('ap', 'rt',
    ...     (5020, 2, 2), (5022,), timedepth=3)
    'ap_rt_5020_*,ap_rt_5021_*'
    >>> format_index_pattern_for_timerange('a', 'b', (1999,), (2002,), timedepth=2)
    'a_b_1999_*,a_b_2000_*,a_b_2001_*'
    >>> format_index_pattern_for_timerange('a', 'b',
    ...     (1999, 27, 17, 0, 3), (1999, 27, 17, 0, 223,), timedepth=5)
    'a_b_1999_27_17_00_*'
    >>> format_index_pattern_for_timerange('a', 'b',
    ...     (1999, 27, 17, 0, 3), (2002, 117, 17, 0, 3), timedepth=5)
    'a_b_1999_*,a_b_2000_*,a_b_2001_*,a_b_2002_*'
    """
    return ",".join(
        _each_indexpattern_for_timerange(
            prefix,
            recordtype,
            from_timeparts,
            until_timeparts,
            timedepth=timedepth,
            max_fanout=max_fanout,
            include_less_granular=include_less_granular,
            only_datelike=only_datelike,
        )
    )


def format_index_pattern_for_range(
    prefix: str,
    recordtype: str,
    from_when: tuple[int, ...] | datetime.date,
    until_when: tuple[int, ...] | datetime.date,
    timedepth: int,
    include_less_granular: bool = False,
) -> str:
    """get an index-name pattern for all indexes within a date range
    >>> format_index_pattern_for_range('ap', 'rt',
    ...     datetime.date(2050, 5, 5), datetime.date(2050, 5, 8),
    ...     timedepth=2)
    'ap_rt_2050_05_*'
    >>> format_index_pattern_for_range('ap', 'rt',
    ...     datetime.date(2050, 5, 5), datetime.date(2050, 5, 8),
    ...     timedepth=2, include_less_granular=True)
    'ap_rt_,ap_rt_2050_,ap_rt_2050_05_*'
    >>> format_index_pattern_for_range('ap', 'rt',
    ...     datetime.date(2050, 5, 5), (2050, 5, 8, 10),
    ...     timedepth=3)
    'ap_rt_2050_05_05_*,ap_rt_2050_05_06_*,ap_rt_2050_05_07_*'
    >>> format_index_pattern_for_range('ap', 'rt',
    ...     (2050, 5, 5, 3), datetime.date(2050, 5, 8),
    ...     timedepth=3, include_less_granular=True)
    'ap_rt_,ap_rt_2050_,ap_rt_2050_05_,ap_rt_2050_05_05_*,ap_rt_2050_05_06_*,ap_rt_2050_05_07_*'
    >>> format_index_pattern_for_range('ap', 'rt',
    ...     (200, 5), datetime.date(200, 5, 8),
    ...     timedepth=3)
    """
    _from_timeparts = (
        timeparts_from_date(from_when, timedepth)
        if isinstance(from_when, datetime.date)
        else from_when
    )
    _until_timeparts = (
        timeparts_from_date(until_when, timedepth)
        if isinstance(until_when, datetime.date)
        else until_when
    )
    return format_index_pattern_for_timerange(
        prefix,
        recordtype,
        _from_timeparts,
        _until_timeparts,
        timedepth=timedepth,
        include_less_granular=include_less_granular,
        only_datelike=True,
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
    >>> parse_index_name('ap_rt_2001')
    ('ap', 'rt', (2001,))
    """
    _prefix, _recordtype, _timename = given_name.split(_DELIMITER, maxsplit=2)
    return (_prefix, _recordtype, tuple(_parse_timename(_timename)))


def parse_index_pattern(given_pattern: str) -> TimeseriesIndexNamePattern:
    """
    >>> parse_index_pattern('blah_fleh_1123_58')
    ('blah', 'fleh', (1123, 58))
    >>> parse_index_pattern('ap_rt_2001_')
    ('ap', 'rt', (2001,))
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
    >>> _format_timename(2345, 0)
    '2345_00'
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

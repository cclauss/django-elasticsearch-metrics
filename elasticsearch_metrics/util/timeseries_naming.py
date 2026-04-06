"""elasticsearch_metrics.util.timeseries_naming

for naming timeseries indexes with lexical time coverage
(so an index-name wildcard can be used to query several indexes)
"""

from __future__ import annotations

__all__ = (
    "format_index_name",
    "format_index_name_for_date",
    "format_index_pattern",
    "format_index_pattern_for_range",
    "format_namepart",
    "format_template_name",
)

import collections
import datetime
import itertools

from .timeparts import (
    timeparts_from_date,
    get_timeparts,
    format_full_timeparts,
    parse_timeparts,
    TIMEPART_DELIMITER,
)

_DELIMITER: str = "_"
_TEMPLATE_NAME_SUFFIX = "_template"
_DEFAULT_PATTERN_FANOUT: int = 3


TimeseriesIndexNamePattern = tuple[str, str, tuple[int, ...]]


def format_index_name(
    app_label: str,
    recordtype: str,
    timeparts: str | collections.abc.Sequence[int] = (),  # empty () -- all time
    max_timedepth: int | None = None,
) -> str:
    """get a full/specific index name, no wildcards or lists

    >>> format_index_name('a', 'rt', (9999, 22))
    'a_rt_9999.22.'
    >>> format_index_name('a', 'rt', (9999, 22, 0))
    'a_rt_9999.22.0.'
    >>> format_index_name('app', 'type', '500.2.3')
    'app_type_500.2.3.'
    >>> format_index_name('app', 'type', ())
    'app_type_'
    """
    _parts = [
        format_namepart(app_label),
        format_namepart(recordtype),
    ]
    _timeparts_seq = (
        parse_timeparts(timeparts) if isinstance(timeparts, str) else timeparts
    )
    if _timeparts_seq:
        _trimmed_timeparts = (
            _timeparts_seq
            if (max_timedepth is None)
            else _timeparts_seq[:max_timedepth]
        )
        _parts.append(_format_timename(*_trimmed_timeparts))
    else:
        _parts.append("")  # add trailing delimiter for unambiguous pattern matching
    return _DELIMITER.join(_parts)


def format_index_name_for_date(
    given_date: datetime.date,
    *,
    app_label: str,
    recordtype: str,
    timedepth: int,
) -> str:
    """get a full/specific index name, no wildcards or lists
    >>> format_index_name_for_date(datetime.date(9876,5,4), app_label='ap', recordtype='rt', timedepth=2)
    'ap_rt_9876.5.'
    """
    return format_index_name(
        app_label, recordtype, timeparts_from_date(given_date, timedepth)
    )


def format_index_pattern(
    app_label: str,
    recordtype: str,
    timeparts: str | collections.abc.Sequence[int] = (),  # empty () -- all time
    max_timedepth: int | None = None,
) -> str:
    """get an index-name pattern for all indexes within the given timeparts
    >>> format_index_pattern('a', 'rt', (9999,22))
    'a_rt_9999.22.*'
    >>> format_index_pattern('a', 'rt', (1, 2, 3, 4, 5))
    'a_rt_1.2.3.4.5.*'
    >>> format_index_pattern('a', 'rt', (1, 2, 3, 4, 5), max_timedepth=3)
    'a_rt_1.2.3.*'
    >>> format_index_pattern('a', 'rt', '5.6.7.8', max_timedepth=3)
    'a_rt_5.6.7.*'
    >>> format_index_pattern('a', 'rt', ())
    'a_rt_*'
    """
    return f"{format_index_name(app_label, recordtype, timeparts, max_timedepth)}*"


def _each_timeparts_for_timerange(
    from_timeparts: collections.abc.Sequence[int],
    until_timeparts: collections.abc.Sequence[int],
    *,
    timedepth: int,
    max_fanout: int,
    include_less_timedepth: bool,
) -> collections.abc.Generator[tuple[tuple[int, ...], bool]]:
    """
    yield (timeparts, is_wildcard) tuples
    """
    if timedepth <= 0:
        yield (), True  # reached timedepth; wildcard
        return
    _from_part, *_from_rest = from_timeparts or [0]
    _until_part, *_until_rest = until_timeparts or [0]
    if include_less_timedepth:
        yield (), False  # include less-granular non-wildcard index, if it exists
    if _from_part == _until_part:
        for _rest_parts, _is_wildcard in _each_timeparts_for_timerange(
            _from_rest,
            _until_rest,
            timedepth=timedepth - 1,
            max_fanout=max_fanout,
            include_less_timedepth=include_less_timedepth,
        ):
            yield (_from_part, *_rest_parts), _is_wildcard
    elif 0 < (_until_part - _from_part) <= max_fanout:  # not too far apart
        for _parallel_part in range(_from_part, _until_part):
            yield (_parallel_part,), True  # wildcard
        if any(_until_rest):  # some of the "until" bucket is included
            _from_zero = tuple(itertools.repeat(0, len(_until_rest)))
            for _rest_parts, _is_wildcard in _each_timeparts_for_timerange(
                _from_zero,
                _until_rest,
                timedepth=timedepth - 1,
                max_fanout=max_fanout,
                include_less_timedepth=include_less_timedepth,
            ):
                yield (_until_part, *_rest_parts), _is_wildcard
    else:  # too far apart
        yield (), True  # wildcard


def _each_indexpattern_for_timerange(
    app_label: str,
    recordtype: str,
    from_timeparts: collections.abc.Sequence[int],
    until_timeparts: collections.abc.Sequence[int],
    *,
    timedepth: int,
    max_fanout: int,
    include_less_timedepth: bool,
    only_datelike: bool,
) -> collections.abc.Generator[str]:
    for _timeparts, _is_wildcard in _each_timeparts_for_timerange(
        from_timeparts,
        until_timeparts,
        timedepth=timedepth,
        max_fanout=max_fanout,
        include_less_timedepth=include_less_timedepth,
    ):
        if only_datelike and (0 in _timeparts[1:3]):
            # intuitively, zero is a fine value for any datepart except the second and third
            continue  # skip month zero and day zero
        if _is_wildcard:
            yield format_index_pattern(app_label, recordtype, _timeparts)
        else:
            yield format_index_name(app_label, recordtype, _timeparts)


def format_index_pattern_for_timeparts_range(
    app_label: str,
    recordtype: str,
    from_timeparts: collections.abc.Sequence[int],
    until_timeparts: collections.abc.Sequence[int],
    *,
    timedepth: int,
    max_fanout: int = _DEFAULT_PATTERN_FANOUT,
    include_less_timedepth: bool = False,
    only_datelike: bool = False,
) -> str:
    """get an index-name pattern for all indexes within a timepart range

    choose a wildcard based on shared timeparts
    >>> format_index_pattern_for_timeparts_range('ap', 'rt',
    ...     (5020, 2, 2), (5020, 12, 20), timedepth=2)
    'ap_rt_5020.*'
    >>> format_index_pattern_for_timeparts_range('ap', 'rt',
    ...     (5020, 2, 2), (5020, 2, 20), timedepth=2)
    'ap_rt_5020.2.*'

    if unshared timeparts close enough, enumerate possibilities to narrow the wildcard
    >>> format_index_pattern_for_timeparts_range('ap', 'rt',
    ...     (5020, 2, 2), (5020, 3, 3), timedepth=3)
    'ap_rt_5020.2.*,ap_rt_5020.3.0.*,ap_rt_5020.3.1.*,ap_rt_5020.3.2.*'

    with `only_datelike=True`, exclude patterns with zero in "month" or "day"
    >>> format_index_pattern_for_timeparts_range('ap', 'rt',
    ...     (5020, 2, 2), (5022, 3, 3), timedepth=3, only_datelike=True)
    'ap_rt_5020.*,ap_rt_5021.*,ap_rt_5022.1.*,ap_rt_5022.2.*,ap_rt_5022.3.1.*,ap_rt_5022.3.2.*'

    with `include_less_timedepth=True`, include patterns for indexes created with lower timedepths
    >>> format_index_pattern_for_timeparts_range('ap', 'rt',
    ...     (5020, 2, 2), (5020, 2, 20), timedepth=2, include_less_timedepth=True)
    'ap_rt_,ap_rt_5020.,ap_rt_5020.2.*'
    """
    return ",".join(
        _each_indexpattern_for_timerange(
            app_label,
            recordtype,
            from_timeparts,
            until_timeparts,
            timedepth=timedepth,
            max_fanout=max_fanout,
            include_less_timedepth=include_less_timedepth,
            only_datelike=only_datelike,
        )
    )


def format_index_pattern_for_range(
    app_label: str,
    recordtype: str,
    from_when: tuple[int, ...] | datetime.date,
    until_when: tuple[int, ...] | datetime.date,
    timedepth: int,
    include_less_timedepth: bool = False,
) -> str:
    """get an index-name pattern for all indexes within a date range

    >>> format_index_pattern_for_range('ap', 'rt',
    ...     datetime.date(2050, 5, 5), datetime.date(2050, 5, 8),
    ...     timedepth=2)
    'ap_rt_2050.5.*'
    >>> format_index_pattern_for_range('ap', 'rt',
    ...     datetime.date(2050, 5, 5), datetime.date(2050, 5, 8),
    ...     timedepth=2, include_less_timedepth=True)
    'ap_rt_,ap_rt_2050.,ap_rt_2050.5.*'
    >>> format_index_pattern_for_range('ap', 'rt',
    ...     datetime.date(2050, 5, 5), (2050, 5, 8, 10),
    ...     timedepth=3)
    'ap_rt_2050.5.5.*,ap_rt_2050.5.6.*,ap_rt_2050.5.7.*'
    >>> format_index_pattern_for_range('ap', 'rt',
    ...     (2050, 5, 5, 3), datetime.date(2050, 5, 8),
    ...     timedepth=3, include_less_timedepth=True)
    'ap_rt_,ap_rt_2050.,ap_rt_2050.5.,ap_rt_2050.5.5.*,ap_rt_2050.5.6.*,ap_rt_2050.5.7.*'
    >>> format_index_pattern_for_range('ap', 'rt',
    ...     (200, 5), datetime.date(200, 5, 8),
    ...     timedepth=3)
    'ap_rt_200.5.*'
    """
    return format_index_pattern_for_timeparts_range(
        app_label=app_label,
        recordtype=recordtype,
        from_timeparts=get_timeparts(from_when, timedepth),
        until_timeparts=get_timeparts(until_when, timedepth),
        timedepth=timedepth,
        include_less_timedepth=include_less_timedepth,
        only_datelike=True,
    )


def format_template_name(
    app_label: str,
    recordtype: str,
) -> str:
    """
    >>> format_template_name('blah', 'fleh')
    'blah_fleh__template'
    """
    return _DELIMITER.join(
        (format_namepart(app_label), format_namepart(recordtype), _TEMPLATE_NAME_SUFFIX)
    )


def format_namepart(namepart: str) -> str:
    return namepart.replace(_DELIMITER, "").lower()


def _format_timename(*timeparts: int) -> str:
    """
    >>> _format_timename(1999)
    '1999.'
    >>> _format_timename(2345)
    '2345.'

    use with any series of integers
    >>> _format_timename(1234, 5, 6, 7)
    '1234.5.6.7.'
    >>> _format_timename(2345, 6, 2, 17, 4200)
    '2345.6.2.17.4200.'
    >>> _format_timename(6, 1, 8, 2)
    '6.1.8.2.'
    >>> _format_timename(2345, 0)
    '2345.0.'
    """
    return f"{format_full_timeparts(timeparts)}{TIMEPART_DELIMITER}"


if __debug__:
    __test__ = {
        "format_index_pattern_for_timeparts_range": """
>>> format_index_pattern_for_timeparts_range('ap', 'rt',
...     (5020, 2, 1), (5020, 3), timedepth=2)
'ap_rt_5020.2.*'
>>> format_index_pattern_for_timeparts_range('ap', 'rt',
...     (5020, 2, 2), (5020, 2, 3), timedepth=3)
'ap_rt_5020.2.2.*'
>>> format_index_pattern_for_timeparts_range('ap', 'rt',
...     (5020, 2, 2), (5022,), timedepth=3)
'ap_rt_5020.*,ap_rt_5021.*'
>>> format_index_pattern_for_timeparts_range('a', 'b', (1999,), (2002,), timedepth=2)
'a_b_1999.*,a_b_2000.*,a_b_2001.*'
>>> format_index_pattern_for_timeparts_range('a', 'b',
...     (1999, 27, 17, 0, 3), (1999, 27, 17, 0, 223,), timedepth=5)
'a_b_1999.27.17.0.*'
>>> format_index_pattern_for_timeparts_range('a', 'b',
...     (1999, 27, 17, 0, 3), (2002, 117, 17, 0, 3), timedepth=5)
'a_b_1999.*,a_b_2000.*,a_b_2001.*,a_b_2002.*'
""",
    }

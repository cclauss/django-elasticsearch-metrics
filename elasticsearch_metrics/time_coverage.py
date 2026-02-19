"""elasticsearch_metrics.time_coverage

for naming timeseries indexes with lexical time coverage
(so an index-name wildcard can be used to query several indexes)

>>> timename(2345)
'2345'

use with any series of integers
>>> timename(2345, 6, 2, 17)
'2345_06_02_17'
>>> timename(6, 1, 8, 2)
'06_01_08_02'

use with dates
>>> timename_from_date(datetime.date(3456, 7, 8), part_count=2)
'3456_07'
>>> timename_from_datestr('3456-07-08', 2)
'3456_07'
>>> timename_from_datestr('3456-07-08', 5)
'3456_07_08_00_00'
>>> timename_from_datestr('2456-07-08T00:01:03+00:00', part_count=5)
'2456_07_08_00_01'
"""

from __future__ import annotations

__all__ = (
    "timename",
    "parse_timename",
    "timename_from_datestr",
    "timename_from_date",
)

from collections.abc import Iterator
import datetime
import itertools

_DELIMITER: str = "_"
_TIMEPART_MIN_LEN: int = 2


def timename(*timeparts: int, delimiter: str = _DELIMITER) -> str:
    """
    >>> timename(1999)
    '1999'
    >>> timename(1234, 5, 6, 7)
    '1234_05_06_07'
    >>> timename(2345, 6, 7, delimiter = '*')
    '2345*06*07'
    """
    return delimiter.join(map(_format_timepart, timeparts))


def parse_timename(given_timename: str, *, delimiter: str = _DELIMITER) -> Iterator[int]:
    """
    >>> list(parse_timename('7766_555_04'))
    [7766, 555, 4]
    >>> list(parse_timename('7766_555'))
    [7766, 555]
    """
    for _part in given_timename.split(delimiter):
        yield int(_part)


def timename_from_datestr(
    given_date: str, part_count: int, *, delimiter: str = _DELIMITER
) -> str:
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
        delimiter=delimiter,
    )


def timename_from_date(
    given_date: datetime.date, part_count: int, *, delimiter: str = _DELIMITER
) -> str:
    """
    >>> timename_from_date(datetime.date(3456, 7, 8), 2)
    '3456_07'
    """
    _timeparts = itertools.islice(_timeparts_from_date(given_date), part_count)
    return timename(*_timeparts, delimiter=delimiter)


def _timeparts_from_date(given_date: datetime.date) -> Iterator[int]:
    yield given_date.year
    yield given_date.month
    yield given_date.day
    if isinstance(given_date, datetime.datetime):
        yield given_date.hour
        yield given_date.minute
        yield given_date.second


def _format_timepart(timepart: int) -> str:
    return f"{timepart:0{_TIMEPART_MIN_LEN}}"

"""elasticsearch_metrics.util.index_name

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

>>> DjelmeIndexName.parse('blarg_myimp_myrecord_1234_56')
"""

from __future__ import annotations

__all__ = (
    "timename",
    "parse_timename",
    "timename_from_datestr",
    "timename_from_date",
)

from collections.abc import Iterator
import dataclasses
import datetime
import itertools

_DELIMITER: str = "_"
_TIMEPART_MIN_LEN: int = 2


@dataclasses.dataclass
class IndexTimesection:
    prefix: str
    imp: str
    recordtype: str
    timeparts: tuple[int, ...] = ()  # empty () -- all time

    @classmethod
    def parse(cls, index_name: str) -> IndexTimesection:
        """
        >>> IndexTimesection.parse('aoeu_myimp_mynote_2001')
        >>> IndexTimesection.parse('aoeu_myimp_mynote_2001')
        """
        _prefix, _imp, _recordtype, _timename = index_name.split(_DELIMITER, maxsplit=2)
        return IndexTimesection(
            _prefix, _imp, _recordtype, tuple(parse_timename(_timename))
        )

    @classmethod
    def format_timepart(cls, timepart: str) -> str:
        return timepart.replace(_DELIMITER, "")

    def as_wildcard(self) -> str:
        """
        >>> IndexTimesection('aoeu', 'myimp', 'mynote', (9999,22)).as_wildcard()
        'aoeu_myimp_mynote_9999_22*'
        """
        return _DELIMITER.join(
            (
                self.format_timepart(_part)
                for _part in (
                    self.prefix,
                    self.imp,
                    self.recordtype,
                    timename(self.timeparts),
                )
            )
        )

    def broaden_time(self) -> IndexTimesection:
        """
        >>> _its = IndexTimesection('aoeu', 'myimp', 'mynote', (9999,22))
        >>> _its.as_wildcard()
        'aoeu_myimp_mynote_9999_22*'
        >>> _its.broaden_time().as_wildcard()
        'aoeu_myimp_mynote_9999*'
        >>> _its.broaden_time().broaden_time().as_wildcard()
        'aoeu_myimp_mynote*'

        but can't broaden_time past recordtype
        >>> _its.broaden_time().broaden_time().broaden_time().as_wildcard()
        'aoeu_myimp_mynote*'
        """
        return dataclasses.replace(self, time_parts=tuple(self.time_parts[:-1]))


def timename(*timeparts: int) -> str:
    """
    >>> timename(1999)
    '1999'
    >>> timename(1234, 5, 6, 7)
    '1234_05_06_07'
    """
    return _DELIMITER.join(map(_format_timepart, timeparts))


def parse_timename(given_timename: str) -> Iterator[int]:
    """
    >>> list(parse_timename('7766_555_04'))
    [7766, 555, 4]
    >>> list(parse_timename('7766_555'))
    [7766, 555]
    """
    for _part in given_timename.split(_DELIMITER):
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
    _timeparts = itertools.islice(_timeparts_from_date(given_date), part_count)
    return timename(*_timeparts)


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

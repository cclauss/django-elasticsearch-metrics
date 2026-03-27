import collections
import datetime
import itertools

__all__ = (
    "get_timeparts",
    "timeparts_from_date",
    "format_timeparts",
    "format_full_timeparts",
    "each_timepart_from_date",
)

TIMEPART_DELIMITER: str = "."


def timeparts_from_date(given_date: datetime.date, timedepth: int) -> tuple[int, ...]:
    """
    >>> timeparts_from_date(datetime.date(3456, 7, 8), 2)
    (3456, 7)
    >>> timeparts_from_date(datetime.date(3456, 7, 8), 4)
    (3456, 7, 8, 0)
    """
    return tuple(
        itertools.islice(
            _zeropadded_timeparts(each_timepart_from_date(given_date)),
            timedepth,
        )
    )


def each_timepart_from_date(given_date: datetime.date) -> collections.abc.Iterator[int]:
    yield given_date.year
    yield given_date.month
    yield given_date.day
    if isinstance(given_date, datetime.datetime):
        yield given_date.hour
        yield given_date.minute
        yield given_date.second


def _zeropadded_timeparts(
    timeparts: collections.abc.Iterable[int],
) -> collections.abc.Iterator[int]:
    yield from timeparts
    yield from itertools.repeat(0)


def get_timeparts(
    when: tuple[int, ...] | datetime.date,
    timedepth: int,
) -> tuple[int, ...]:
    return (
        timeparts_from_date(when, timedepth)
        if isinstance(when, datetime.date)
        else tuple(itertools.islice(_zeropadded_timeparts(when), timedepth))
    )


def format_full_timeparts(when: tuple[int, ...] | datetime.date) -> str:
    """
    >>> format_full_timeparts((3000, 2))
    '3000.2'
    >>> format_full_timeparts(datetime.date(3000, 7, 12))
    '3000.7.12'
    >>> format_full_timeparts(datetime.datetime(3000, 9, 1))
    '3000.9.1.0.0.0'
    """
    _parts = (
        timeparts_from_date(
            when, timedepth=(6 if isinstance(when, datetime.datetime) else 3)
        )
        if isinstance(when, datetime.date)
        else when
    )
    return TIMEPART_DELIMITER.join(map(str, _parts))


def format_timeparts(when: tuple[int, ...] | datetime.date, timedepth: int) -> str:
    """
    >>> format_timeparts(datetime.date(3000, 7, 12), timedepth=3)
    '3000.7.12'
    >>> format_timeparts(datetime.date(3000, 7, 12), timedepth=2)
    '3000.7'
    >>> format_timeparts(datetime.date(3000, 7, 12), timedepth=1)
    '3000'
    """
    return format_full_timeparts(get_timeparts(when, timedepth))


def parse_timeparts(timepart_str: str) -> tuple[int, ...]:
    """
    >>> parse_timeparts('1.2.3')
    (1, 2, 3)
    >>> parse_timeparts('1999.12.7.9')
    (1999, 12, 7, 9)
    >>> parse_timeparts('')
    ()
    """
    _split_parts = timepart_str.split(TIMEPART_DELIMITER)
    if not any(_split_parts):
        return ()
    return tuple(map(int, _split_parts))


if __debug__:
    __test__ = {
        "format_timeparts": """
>>> format_timeparts((3000, 2, 7, 9), timedepth=2)
'3000.2'
>>> format_timeparts((3000, 2), timedepth=1)
'3000'
>>> format_timeparts((3000, 2, 7, 9), timedepth=5)
'3000.2.7.9.0'
>>> format_timeparts(datetime.datetime(3000, 9, 1, 5, 2), timedepth=6)
'3000.9.1.5.2.0'
>>> format_timeparts(datetime.datetime(3000, 9, 1, 5, 2), timedepth=3)
'3000.9.1'
""",
    }

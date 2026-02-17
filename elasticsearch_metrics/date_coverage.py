"""elasticsearch_metrics.date_coverage: for naming timeseries indexes

>>> date_coverage('2345')
>>> date_coverage('2345_06')
>>> date_coverage('2345_06_01')
"""
from __future__ import annotations
import calendar
import dataclasses
import datetime
import re
import typing


def date_coverage(coverage_str: str) -> ProtoDateCoverage:
    for _coverage_cls in (YearCoverage, YearMonthCoverage, YearMonthDayCoverage):
        try:
            return _coverage_cls.from_str(coverage_str)
        except ValueError:
            pass
    raise ValueError(f"cannot parse {coverage_str!r} into date coverage")


@typing.runtime_checkable
class ProtoDateCoverage(typing.Protocol):
    def __init__(self, *args: str) -> None: ...

    @classmethod
    def from_str(cls, given_str: str) -> typing.Self:
        """construct from a string from an index name"""

    @classmethod
    def from_date(cls, date: datetime.date) -> typing.Self:
        """construct from a `date` (or `datetime`)"""

    def __str__(self) -> str:
        """convert to string (inverse of cls.from_str)"""

    def coverage_start(self) -> datetime.datetime:
        """get a datetime (in UTC timezone) when this coverage starts"""

    def coverage_end(self) -> datetime.datetime:
        """get a datetime (in UTC timezone) when this coverage ends (the start of next coverage)"""

    def next(self) -> typing.Self: ...

    def prior(self) -> typing.Self: ...


@dataclasses.dataclass(frozen=True)
class YearCoverage(ProtoDateCoverage):
    DATE_COVERAGE_RE = re.compile(r"(\d{4,})")

    year: int

    @classmethod
    def from_str(cls, given_str: str) -> typing.Self:
        """construct from a string from an index name"""
        # assumes groups in DATE_COVERAGE_RE map to positional args
        if _match := cls.DATE_COVERAGE_RE.fullmatch(given_str):
            return cls(*map(int, _match.groups()))
        raise ValueError(f"invalid str for {cls.__name__}: {given_str!r}")

    @classmethod
    def from_date(cls, given_date: datetime.date) -> typing.Self:
        if isinstance(given_date, datetime.datetime):
            _as_utc = given_date.astimezone(datetime.UTC)
            _year = _as_utc.year
        else:
            _year = given_date.year
        return cls(_year)

    def __str__(self) -> str:
        return str(self.year)

    def coverage_start(self) -> datetime.datetime:
        return datetime.datetime(self.year, 1, 1, tzinfo=datetime.UTC)

    def coverage_end(self) -> datetime.datetime:
        return self.next().coverage_start()

    def next(self) -> typing.Self:
        return dataclasses.replace(self, year=(self.year + 1))

    def prior(self) -> typing.Self:
        return dataclasses.replace(self, year=(self.year - 1))


@dataclasses.dataclass(frozen=True)
class YearMonthCoverage(YearCoverage):
    _DELIMITER: typing.ClassVar[str] = "_"
    DATE_COVERAGE_RE = re.compile(_DELIMITER.join((r"(\d{4,})", r"(\d\d)")))

    month: int

    @classmethod
    def from_date(cls, given_date: datetime.date) -> typing.Self:
        if isinstance(given_date, datetime.datetime):
            _as_utc = given_date.astimezone(datetime.UTC)
            _year, _month = (_as_utc.year, _as_utc.month)
        else:
            _year, _month = (given_date.year, given_date.month)
        return cls(_year, _month)

    def __str__(self) -> str:
        return self._DELIMITER.join((str(self.year), str(self.month)))

    def coverage_start(self) -> datetime.datetime:
        return datetime.datetime(self.year, self.month, 1, tzinfo=datetime.UTC)

    def next(self) -> typing.Self:
        return (
            dataclasses.replace(self, year=(self.year + 1), month=int(calendar.JANUARY))
            if self.month == calendar.DECEMBER
            else dataclasses.replace(self, month=self.month + 1)
        )

    def prior(self) -> typing.Self:
        return (
            dataclasses.replace(
                self, year=(self.year - 1), month=int(calendar.DECEMBER)
            )
            if self.month == calendar.JANUARY
            else dataclasses.replace(self, month=self.month - 1)
        )


@dataclasses.dataclass(frozen=True)
class YearMonthDayCoverage(YearMonthCoverage):
    DATE_COVERAGE_RE = re.compile(
        YearMonthCoverage._DELIMITER.join((r"(\d{4,})", r"(\d\d)", r"(\d\d)"))
    )

    day: int

    @classmethod
    def from_date(cls, given_date: datetime.date) -> typing.Self:
        if isinstance(given_date, datetime.datetime):
            _as_utc = given_date.astimezone(datetime.UTC)
            _year, _month, _day = (_as_utc.year, _as_utc.month, _as_utc.day)
        else:
            _year, _month, _day = (given_date.year, given_date.month, given_date.day)
        return cls(_year, _month, _day)

    def __str__(self) -> str:
        return self._DELIMITER.join((str(self.year), str(self.month), str(self.day)))

    def as_date(self) -> datetime.date:
        return datetime.date(self.year, self.month, self.day)

    def coverage_start(self) -> datetime.datetime:
        return datetime.datetime(self.year, self.month, self.day, tzinfo=datetime.UTC)

    def next(self) -> typing.Self:
        return self.from_date(self.as_date() + datetime.timedelta(days=1))

    def prior(self) -> typing.Self:
        return self.from_date(self.as_date() - datetime.timedelta(days=1))

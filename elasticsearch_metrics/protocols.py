from __future__ import annotations
import collections
import typing

__all__ = (
    "ProtoTimeseriesImp",
    "ProtoTimeseriesImpModule",
)


class ProtoTimeseriesImp(typing.Protocol):
    @property
    def imp_name(self) -> str: ...
    @property
    def imp_kwargs(self) -> dict[str, str]: ...

    def each_timeseries_record_type(
        self,
    ) -> collections.abc.Iterator[type[ProtoTimeseriesRecord]]: ...
    def each_timeseries_index(self): ...

    #
    def show_timeseries_indexes(self): ...
    def setup_timeseries_indexes(self) -> None: ...
    def teardown_timeseries_indexes(self) -> None: ...
    def record_timeseries_record(self, record_doc: ProtoTimeseriesRecord) -> ...: ...
    def check_timeseries_indexes(self): ...


class ProtoTimeseriesRecord(typing.Protocol):
    @classmethod
    def record(cls): ...


@typing.runtime_checkable
class ProtoTimeseriesImpModule(typing.Protocol):
    @staticmethod
    def djelme_imp(
        imp_name: str,
        imp_kwargs: dict[str, str],
        namespace_prefix: str = "",
    ) -> ProtoTimeseriesImp: ...

    @staticmethod
    def djelme_when_ready(imps: collections.abc.Iterable[ProtoTimeseriesImp]) -> None: ...

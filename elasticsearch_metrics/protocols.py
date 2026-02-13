from __future__ import annotations
from collections.abc import Iterator
import typing

__all__ = (
    "ProtoTimeseriesImp",
    "ProtoTimeseriesImpModule",
)


class ProtoTimeseriesImp(typing.Protocol):
    def show_timeseries_indexes(self): ...
    def setup_timeseries_indexes(self) -> None: ...
    def teardown_timeseries_indexes(self) -> None: ...
    def record_timeseries_record(self, record_doc: ProtoTimeseriesRecord) -> ...: ...
    def check_timeseries_indexes(self): ...
    def each_timeseries_record_type(self) -> Iterator[type[ProtoTimeseriesRecord]]: ...


class ProtoTimeseriesRecord(typing.Protocol):
    @classmethod
    def record(cls): ...


@typing.runtime_checkable
class ProtoTimeseriesImpModule(typing.Protocol):
    @staticmethod
    def djelme_imp_from_config(
        imp_name: str,
        imp_config: dict[str, str],
        namespace_prefix: str = "",
    ) -> ProtoTimeseriesImp: ...

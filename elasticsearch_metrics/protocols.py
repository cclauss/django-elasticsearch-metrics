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

    def setup_timeseries_indexes(self) -> None: ...
    def teardown_timeseries_indexes(self) -> None: ...

    # def each_timeseries_recordtype(
    #     self,
    # ) -> collections.abc.Iterable[type[ProtoTimeseriesRecord]]: ...
    # def get_timeseries_recordtype(
    #     self, recordtype_name: str
    # ) -> type[ProtoTimeseriesRecord]: ...
    # def show_timeseries_indexes(self): ...
    # def record_timeseries_record(self, record_doc: ProtoTimeseriesRecord) -> ...: ...
    # def check_timeseries_indexes(self): ...


class ProtoTimeseriesRecord(typing.Protocol):
    ...
    # @classmethod
    # def record(cls): ...

    @classmethod
    def each_timeseries_index_status(cls) -> collections.abc.Iterable[str]: ...


@typing.runtime_checkable
class ProtoTimeseriesImpModule(typing.Protocol):
    @staticmethod
    def djelme_imp(
        imp_name: str,
        imp_kwargs: dict[str, str],
        namespace_prefix: str = "",
    ) -> ProtoTimeseriesImp:
        """djelme_imp: impstantiate a djelme implementation"""

    @staticmethod
    def djelme_when_ready(
        imps: collections.abc.Iterable[ProtoTimeseriesImp],
    ) -> None:
        """djelme_when_ready: recordtypes and djelme config loaded -- here's one of each imp"""

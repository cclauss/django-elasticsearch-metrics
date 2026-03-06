from __future__ import annotations
import collections
import typing

__all__ = (
    "ProtoDjelmeBackend",
    "ProtoDjelmeImp",
)


class ProtoDjelmeBackend(typing.Protocol):
    @property
    def backend_name(self) -> str: ...
    @property
    def imp_kwargs(self) -> dict[str, str]: ...

    def setup_timeseries_indexes(
        self, recordtypes: collections.abc.Iterable[type[ProtoTimeseriesRecord]] = ()
    ) -> None: ...
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
    @classmethod
    def record(cls, **kwargs): ...

    @classmethod
    def each_timeseries_index_status(cls) -> collections.abc.Iterable[str]: ...

    @classmethod
    def check_timeseries_setup(cls, using=None): ...


@typing.runtime_checkable
class ProtoDjelmeImp(typing.Protocol):
    @staticmethod
    def djelme_backend(
        backend_name: str,
        imp_kwargs: dict[str, str],
        namespace_prefix: str = "",
    ) -> ProtoDjelmeBackend:
        """djelme_backend: impstantiate a djelme backend"""

    @staticmethod
    def djelme_when_ready(
        backends: collections.abc.Iterable[ProtoDjelmeBackend],
    ) -> None:
        """djelme_when_ready: recordtypes and djelme config loaded -- here's one of each backend"""


class ProtoCountedUsage(typing.Protocol):
    """
    fields correspond to defined terms from COUNTER
    https://cop5.projectcounter.org/en/5.0.2/appendices/a-glossary-of-terms.html
    """

    # counter:Platform
    platform_iri: str
    # counter:Database
    database_iri: str
    # counter:Session
    sessionhour_id: str
    # counter:Item
    item_iri: str
    # within_iris corresponds roughly to counter:Title, but as a more
    # inclusive within/part-of/contained-by relationship
    within_iris: list[str]

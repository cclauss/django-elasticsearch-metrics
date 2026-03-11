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

    def djelme_setup(self, recordtypes: collections.abc.Iterable[type]) -> None: ...

    def djelme_teardown(self, recordtypes: collections.abc.Iterable[type]) -> None: ...

    # def get_timeseries_recordtype(
    #     self, recordtype_name: str
    # ) -> type[ProtoDjelmeRecord]: ...
    # def show_timeseries_indexes(self): ...
    # def record_timeseries_record(self, record_doc: ProtoDjelmeRecord) -> ...: ...
    # def check_timeseries_indexes(self): ...


class ProtoDjelmeRecord(typing.Protocol):
    @classmethod
    def record(
        cls, **kwargs: typing.Any
    ) -> "typing.Self":  # typing.Self added in py 3.11 -- str annotation until 3.10 eol
        ...

    # @classmethod
    # def each_timeseries_index_status(cls) -> collections.abc.Iterable[str]: ...
    @classmethod
    def check_djelme_setup(cls, using: str | None = None) -> bool: ...


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


###
# counter?


class ProtoCountedUsage(typing.Protocol):
    """
    fields correspond to defined terms from COUNTER
    https://cop5.projectcounter.org/en/5.0.2/appendices/a-glossary-of-terms.html
    """

    platform_iri: str  # counter:Platform
    database_iri: str  # counter:Database
    sessionhour_id: str  # counter:Session
    item_iri: str  # counter:Item

    # within_iris corresponds roughly to counter:Title, but as a more
    # inclusive within/part-of/contained-by relationship
    within_iris: list[str]

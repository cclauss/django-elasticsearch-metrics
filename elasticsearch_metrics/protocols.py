from __future__ import annotations
import typing


class ProtoDjelmetricsImp(typing.Protocol):
    def setup_db(self) -> None: ...
    def teardown_db(self) -> None: ...
    # def save_event_log(self, event_log: ProtoEventLog) -> None: ...
    # def save_report(self, report: ProtoReport) -> None: ...
    # def iter_reports(self, report_name: str) -> Iterator[ProtoReport]: ...


@typing.runtime_checkable
class ProtoDjelmetricsImpModule(typing.Protocol):
    @staticmethod
    def djelme_imp_from_config(
        imp_name: str,
        imp_config: dict[str, str],
    ) -> ProtoDjelmetricsImp:
        ...


# class ProtoEventLog(typing.Protocol):
#     @property
#     def timestamp(self) -> datetime.datetime:
#         ...
#
#     @property
#     def event_name(self) -> str:
#         ...
#

# class ProtoPeriodicReport(typing.Protocol):
#     @property
#     def timestamp(self) -> datetime.datetime:
#         ...
#
#     @property
#     def report_timerange(self) -> datetime.date | YearMonth:
#         ...
#
#     @property
#     def report_name(self) -> str:
#         ...

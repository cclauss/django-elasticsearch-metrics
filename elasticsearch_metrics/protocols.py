from __future__ import annotations
import typing


class ProtoDjelmetricsImp(typing.Protocol):
    def setup_db(self) -> None: ...
    def teardown_db(self) -> None: ...


@typing.runtime_checkable
class ProtoDjelmetricsImpModule(typing.Protocol):
    @staticmethod
    def djelme_imp_from_config(
        imp_name: str,
        imp_config: dict[str, str],
    ) -> ProtoDjelmetricsImp: ...

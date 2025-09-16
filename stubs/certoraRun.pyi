from typing import List, Optional, Protocol
from pathlib import Path

class CertoraRunResult(Protocol):
    @property
    def link(self) -> Optional[str]:
        ...

    @property
    def is_local_link(self) -> bool:
        ...

    @property
    def src_dir(self) -> Path:
        ...

    @property
    def rule_report_link(self) -> Optional[str]:
        ...

def run_certora(args: List[str]) -> Optional[CertoraRunResult]:
    ...

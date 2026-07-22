from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ConversionStatus(StrEnum):
    WAITING = "대기"
    CONVERTING = "변환 중"
    SUCCESS = "성공"
    FAILED = "실패"
    SKIPPED = "건너뜀"


@dataclass(slots=True)
class ConversionItem:
    source_path: Path
    page_range: str = "전체"
    status: ConversionStatus = ConversionStatus.WAITING
    output_path: Path | None = None
    error: str = ""

    @property
    def filename(self) -> str:
        return self.source_path.name

    @property
    def extension(self) -> str:
        return self.source_path.suffix.lower().lstrip(".").upper()

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ConversionOptions:
    output_directory: Path
    page_range: str = "전체"
    quality: str = "일반"
    color_mode: str = "컬러"


class BaseConverter(ABC):
    supported_extensions: frozenset[str] = frozenset()

    def supports(self, source: Path) -> bool:
        return source.suffix.lower() in self.supported_extensions

    @abstractmethod
    def convert(self, source: Path, options: ConversionOptions) -> Path:
        raise NotImplementedError

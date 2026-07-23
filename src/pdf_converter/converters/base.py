from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable

from pdf_converter.converters.common import finalize_exported_pdf


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

    def _export_and_finalize(
        self,
        source: Path,
        options: ConversionOptions,
        exporter: Callable[[Path], None],
    ) -> Path:
        options.output_directory.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix="pdf_converter_") as temporary_directory:
            exported_pdf = Path(temporary_directory) / "export.pdf"
            exporter(exported_pdf)
            if not exported_pdf.is_file():
                raise RuntimeError("PDF 내보내기 결과 파일이 생성되지 않았습니다.")
            return finalize_exported_pdf(exported_pdf, source, options)

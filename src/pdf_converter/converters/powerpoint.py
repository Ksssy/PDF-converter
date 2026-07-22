from __future__ import annotations

from contextlib import suppress
from pathlib import Path

import pythoncom
from win32com.client import DispatchEx

from pdf_converter.converters.base import BaseConverter, ConversionOptions


class PowerPointConverter(BaseConverter):
    supported_extensions = frozenset({".ppt", ".pptx", ".pptm", ".pps", ".ppsx"})

    def convert(self, source: Path, options: ConversionOptions) -> Path:
        if options.color_mode == "흑백":
            raise RuntimeError("PowerPoint 흑백 PDF 변환은 아직 지원하지 않습니다.")

        def export(target: Path) -> None:
            pythoncom.CoInitialize()
            application = None
            presentation = None
            try:
                application = DispatchEx("PowerPoint.Application")
                presentation = application.Presentations.Open(
                    str(source.resolve()),
                    ReadOnly=True,
                    Untitled=False,
                    WithWindow=False,
                )
                presentation.PrintOptions.PrintHiddenSlides = False
                presentation.SaveAs(str(target), 32)
            except Exception as error:
                raise RuntimeError(f"PowerPoint PDF 변환 실패: {error}") from error
            finally:
                if presentation is not None:
                    with suppress(Exception):
                        presentation.Close()
                if application is not None:
                    with suppress(Exception):
                        application.Quit()
                pythoncom.CoUninitialize()

        return self._export_and_finalize(source, options, export)

from __future__ import annotations

from contextlib import suppress
from pathlib import Path

import pythoncom
from win32com.client import DispatchEx

from pdf_converter.converters.base import BaseConverter, ConversionOptions


class WordConverter(BaseConverter):
    supported_extensions = frozenset({".doc", ".docx"})

    def convert(self, source: Path, options: ConversionOptions) -> Path:
        def export(target: Path) -> None:
            pythoncom.CoInitialize()
            application = None
            document = None
            try:
                application = DispatchEx("Word.Application")
                application.Visible = False
                application.DisplayAlerts = 0
                document = application.Documents.Open(
                    str(source.resolve()),
                    ReadOnly=True,
                    AddToRecentFiles=False,
                )
                document.ExportAsFixedFormat(
                    OutputFileName=str(target),
                    ExportFormat=17,
                    OpenAfterExport=False,
                    OptimizeFor=1 if options.quality == "최소용량" else 0,
                    Range=0,
                    Item=0,
                    IncludeDocProps=True,
                    KeepIRM=True,
                    CreateBookmarks=1,
                    DocStructureTags=True,
                    BitmapMissingFonts=True,
                    UseISO19005_1=False,
                )
            except Exception as error:
                raise RuntimeError(f"Word PDF 변환 실패: {error}") from error
            finally:
                if document is not None:
                    with suppress(Exception):
                        document.Close(False)
                if application is not None:
                    with suppress(Exception):
                        application.Quit()
                pythoncom.CoUninitialize()

        return self._export_and_finalize(source, options, export)

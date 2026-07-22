from __future__ import annotations

from contextlib import suppress
from pathlib import Path

import pythoncom
from win32com.client import DispatchEx

from pdf_converter.converters.base import BaseConverter, ConversionOptions


class ExcelConverter(BaseConverter):
    supported_extensions = frozenset({".xls", ".xlsx", ".xlsm", ".xlsb"})

    def convert(self, source: Path, options: ConversionOptions) -> Path:
        def export(target: Path) -> None:
            pythoncom.CoInitialize()
            application = None
            workbook = None
            try:
                application = DispatchEx("Excel.Application")
                application.Visible = False
                application.DisplayAlerts = False
                application.EnableEvents = False
                application.AskToUpdateLinks = False
                workbook = application.Workbooks.Open(
                    str(source.resolve()),
                    UpdateLinks=0,
                    ReadOnly=True,
                    IgnoreReadOnlyRecommended=True,
                    AddToMru=False,
                )
                if options.color_mode == "흑백":
                    for worksheet in workbook.Worksheets:
                        worksheet.PageSetup.BlackAndWhite = True
                workbook.ExportAsFixedFormat(
                    Type=0,
                    Filename=str(target),
                    Quality=1 if options.quality == "최소용량" else 0,
                    IncludeDocProperties=True,
                    IgnorePrintAreas=False,
                    OpenAfterPublish=False,
                )
            except Exception as error:
                raise RuntimeError(f"Excel PDF 변환 실패: {error}") from error
            finally:
                if workbook is not None:
                    with suppress(Exception):
                        workbook.Close(False)
                if application is not None:
                    with suppress(Exception):
                        application.Quit()
                pythoncom.CoUninitialize()

        return self._export_and_finalize(source, options, export)

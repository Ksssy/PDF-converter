from __future__ import annotations

import re
from contextlib import suppress
from pathlib import Path

import pythoncom
from win32com.client import DispatchEx

from pdf_converter.core.models import ExcelValidationIssue


EXCEL_EXTENSIONS = frozenset({".xls", ".xlsx", ".xlsm", ".xlsb"})
EXCEL_ERROR_LABELS = ("#####", "#N/A", "#DIV/0!", "#NAME?", "#VALUE!")
EXCEL_ERROR_HELP_TEXT = (
    "엑셀 주요 오류: ##### (열 너비·날짜/시간 표시), "
    "#N/A (참조 값 없음), #DIV/0! (0으로 나눔), "
    "#NAME? (함수·이름 오류), #VALUE! (인수 형식 오류)"
)

XL_CELL_TYPE_CONSTANTS = 2
XL_CELL_TYPE_FORMULAS = -4123


def is_excel_source(source: Path) -> bool:
    return source.suffix.lower() in EXCEL_EXTENSIONS


def inspect_excel_for_errors(source: Path) -> list[ExcelValidationIssue]:
    """Inspect displayed values in the source workbook and return cell locations."""
    pythoncom.CoInitialize()
    application = None
    workbook = None
    try:
        application = DispatchEx("Excel.Application")
        application.Visible = False
        application.DisplayAlerts = False
        application.EnableEvents = False
        application.AskToUpdateLinks = False
        with suppress(Exception):
            application.AutomationSecurity = 3

        workbook = application.Workbooks.Open(
            str(source.resolve()),
            UpdateLinks=0,
            ReadOnly=True,
            IgnoreReadOnlyRecommended=True,
            AddToMru=False,
        )
        with suppress(Exception):
            application.CalculateFull()

        issues: list[ExcelValidationIssue] = []
        for worksheet in workbook.Worksheets:
            sheet_issues: list[ExcelValidationIssue] = []
            seen_addresses: set[str] = set()
            used_range = worksheet.UsedRange
            for cell_type in (
                XL_CELL_TYPE_CONSTANTS,
                XL_CELL_TYPE_FORMULAS,
            ):
                try:
                    cells = used_range.SpecialCells(cell_type).Cells
                except Exception:
                    continue
                for cell in cells:
                    address = str(cell.Address).replace("$", "")
                    if address in seen_addresses:
                        continue
                    label = classify_excel_display_text(str(cell.Text))
                    if label is None:
                        continue
                    seen_addresses.add(address)
                    column = int(cell.Column)
                    sheet_issues.append(
                        ExcelValidationIssue(
                            sheet_name=str(worksheet.Name),
                            row=int(cell.Row),
                            column=column,
                            column_name=excel_column_name(column),
                            address=address,
                            label=label,
                        )
                    )
            issues.extend(
                sorted(
                    sheet_issues,
                    key=lambda issue: (issue.row, issue.column, issue.label),
                )
            )
        return issues
    except Exception as error:
        raise RuntimeError(f"Excel 원본 오류 검사 실패: {error}") from error
    finally:
        if workbook is not None:
            with suppress(Exception):
                workbook.Close(False)
        if application is not None:
            with suppress(Exception):
                application.Quit()
        pythoncom.CoUninitialize()


def classify_excel_display_text(display_text: str) -> str | None:
    text = display_text.strip().upper()
    if re.fullmatch(r"#{3,}", text):
        return "#####"
    if text in EXCEL_ERROR_LABELS[1:]:
        return text
    return None


def excel_column_name(column: int) -> str:
    if column < 1:
        raise ValueError("Excel 열 번호는 1 이상이어야 합니다.")
    name = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        name = chr(65 + remainder) + name
    return name

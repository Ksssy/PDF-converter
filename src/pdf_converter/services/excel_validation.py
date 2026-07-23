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
EXCEL_VALIDATION_FAST = "fast"
EXCEL_VALIDATION_PRECISE = "precise"
EXCEL_FAST_HELP_TEXT = (
    "빠른 검사: 마지막 저장 결과를 다시 계산하지 않고 검사합니다. "
    "빠르지만 저장 후 계산되지 않은 오류는 놓칠 수 있습니다."
)
EXCEL_PRECISE_HELP_TEXT = (
    "정밀 검사: 모든 수식을 다시 계산한 뒤 검사합니다. "
    "최신 계산 오류를 찾지만 수식이 많은 파일은 오래 걸립니다."
)
EXCEL_SCOPE_HELP_TEXT = (
    "검사 범위: 인쇄영역으로 지정된 보이는 셀만 검사합니다. "
    "인쇄영역이 없는 시트와 숨김 시트·행·열·접힌 그룹은 제외합니다."
)

XL_CELL_TYPE_CONSTANTS = 2
XL_CELL_TYPE_FORMULAS = -4123
XL_CELL_TYPE_VISIBLE = 12
XL_CALCULATION_MANUAL = -4135
XL_SHEET_VISIBLE = -1


def is_excel_source(source: Path) -> bool:
    return source.suffix.lower() in EXCEL_EXTENSIONS


def inspect_excel_for_errors(
    source: Path,
    *,
    recalculate: bool = False,
) -> list[ExcelValidationIssue]:
    """Inspect visible print-area cells and return their Excel error locations."""
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
        with suppress(Exception):
            application.Calculation = XL_CALCULATION_MANUAL

        workbook = application.Workbooks.Open(
            str(source.resolve()),
            UpdateLinks=0,
            ReadOnly=True,
            IgnoreReadOnlyRecommended=True,
            AddToMru=False,
        )
        if recalculate:
            application.CalculateFull()

        issues: list[ExcelValidationIssue] = []
        for worksheet in workbook.Worksheets:
            if int(worksheet.Visible) != XL_SHEET_VISIBLE:
                continue
            visible_print_range = _get_visible_print_range(worksheet)
            if visible_print_range is None:
                continue

            sheet_issues: list[ExcelValidationIssue] = []
            seen_addresses: set[str] = set()
            for cell_type in (
                XL_CELL_TYPE_CONSTANTS,
                XL_CELL_TYPE_FORMULAS,
            ):
                try:
                    cells = visible_print_range.SpecialCells(cell_type).Cells
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


def _get_visible_print_range(worksheet):
    try:
        print_area = str(worksheet.PageSetup.PrintArea or "").strip()
        if not print_area:
            return None
        return worksheet.Range(print_area).SpecialCells(XL_CELL_TYPE_VISIBLE)
    except Exception:
        return None


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

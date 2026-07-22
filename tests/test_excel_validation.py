from pathlib import Path

import pytest

from pdf_converter.core.models import ConversionItem, ExcelValidationIssue
from pdf_converter.services.excel_validation import (
    classify_excel_display_text,
    excel_column_name,
    is_excel_source,
)


@pytest.mark.parametrize(
    ("display_text", "expected"),
    [
        ("#######", "#####"),
        ("#N/A", "#N/A"),
        ("#DIV/0!", "#DIV/0!"),
        ("#NAME?", "#NAME?"),
        ("#VALUE!", "#VALUE!"),
        ("123.45", None),
        ("OK", None),
    ],
)
def test_classify_excel_display_text(
    display_text: str,
    expected: str | None,
) -> None:
    assert classify_excel_display_text(display_text) == expected


@pytest.mark.parametrize(
    ("column", "expected"),
    [(1, "A"), (26, "Z"), (27, "AA"), (52, "AZ"), (53, "BA")],
)
def test_excel_column_name(column: int, expected: str) -> None:
    assert excel_column_name(column) == expected


def test_excel_issue_summary_includes_sheet_row_column_and_address() -> None:
    item = ConversionItem(Path("calculation.xlsx"), validation_checked=True)
    item.excel_validation_issues = [
        ExcelValidationIssue(
            sheet_name="교량 계산",
            row=12,
            column=2,
            column_name="B",
            address="B12",
            label="#DIV/0!",
        )
    ]

    assert item.validation_summary == (
        "엑셀 [교량 계산] 12행 B열(B12): #DIV/0!"
    )
    assert item.validation_issue_count == 1


def test_excel_source_extensions() -> None:
    assert is_excel_source(Path("calculation.xlsx"))
    assert is_excel_source(Path("legacy.xls"))
    assert is_excel_source(Path("binary.xlsb"))
    assert not is_excel_source(Path("report.docx"))

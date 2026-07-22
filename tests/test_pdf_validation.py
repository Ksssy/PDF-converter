from pathlib import Path

import pymupdf

from pdf_converter.core.models import ConversionItem
from pdf_converter.services.pdf_validation import (
    HASH_RULE_LABEL,
    NG_RULE_LABEL,
    QUESTION_RULE_LABEL,
    build_validation_terms,
    inspect_pdf_for_errors,
)


def test_build_validation_terms_only_includes_selected_and_custom() -> None:
    terms = build_validation_terms(
        check_ng=True,
        check_hashes=False,
        check_questions=True,
        custom_terms="#VALUE!, ERROR; error",
    )

    assert terms == [NG_RULE_LABEL, QUESTION_RULE_LABEL, "#VALUE!", "ERROR"]


def test_pdf_validation_reports_errors_by_page(tmp_path: Path) -> None:
    pdf_path = tmp_path / "calculation.pdf"
    with pymupdf.open() as document:
        first_page = document.new_page()
        first_page.insert_text(
            (72, 72),
            "RESULT NG / CHECK N.G / ENGINEERING",
        )
        second_page = document.new_page()
        second_page.insert_text((72, 72), "## ?? ERROR")
        document.new_page()
        document.save(pdf_path)

    report = inspect_pdf_for_errors(
        pdf_path,
        [NG_RULE_LABEL, HASH_RULE_LABEL, QUESTION_RULE_LABEL, "ERROR"],
    )

    assert [(issue.page_number, issue.label, issue.count) for issue in report.issues] == [
        (1, NG_RULE_LABEL, 2),
        (2, HASH_RULE_LABEL, 1),
        (2, QUESTION_RULE_LABEL, 1),
        (2, "ERROR", 1),
    ]
    assert report.unsearchable_pages == [3]


def test_conversion_item_formats_validation_summary() -> None:
    item = ConversionItem(Path("calculation.xlsx"), validation_checked=True)
    item.validation_issues = [
        _issue(2, NG_RULE_LABEL, 3),
        _issue(5, HASH_RULE_LABEL, 1),
    ]
    item.validation_unsearchable_pages = [7, 8, 9]

    assert item.validation_issue_count == 4
    assert item.validation_summary == (
        "2페이지: NG / N.G 3건 | 5페이지: ## 1건 | "
        "텍스트 검색 불가: 7-9페이지"
    )


def _issue(page_number: int, label: str, count: int):
    from pdf_converter.core.models import PdfValidationIssue

    return PdfValidationIssue(page_number, label, count)

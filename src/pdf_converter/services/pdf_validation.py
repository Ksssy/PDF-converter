from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from pdf_converter.core.models import PdfValidationIssue


NG_RULE_LABEL = "NG / N.G"
HASH_RULE_LABEL = "##"
QUESTION_RULE_LABEL = "??"
EXCEL_HASH_RULE_LABEL = "엑셀 ##### 오류"
EXCEL_ERROR_TERMS = (
    EXCEL_HASH_RULE_LABEL,
    "#N/A",
    "#DIV/0!",
    "#NAME?",
    "#VALUE!",
)


@dataclass(frozen=True, slots=True)
class PdfValidationReport:
    issues: list[PdfValidationIssue]
    unsearchable_pages: list[int]


def build_validation_terms(
    check_ng: bool,
    check_hashes: bool,
    check_questions: bool,
    custom_terms: str = "",
    check_excel_errors: bool = False,
) -> list[str]:
    terms: list[str] = []
    if check_ng:
        terms.append(NG_RULE_LABEL)
    if check_hashes:
        terms.append(HASH_RULE_LABEL)
    if check_questions:
        terms.append(QUESTION_RULE_LABEL)
    if check_excel_errors:
        terms.extend(EXCEL_ERROR_TERMS)

    terms.extend(
        term.strip()
        for term in re.split(r"[,;\n]", custom_terms)
        if term.strip()
    )

    unique_terms: list[str] = []
    seen: set[str] = set()
    for term in terms:
        key = term.casefold()
        if key not in seen:
            seen.add(key)
            unique_terms.append(term)
    return unique_terms


def inspect_pdf_for_errors(
    pdf_path: Path,
    terms: list[str],
) -> PdfValidationReport:
    rules = [(term, _compile_term(term)) for term in terms]
    issues: list[PdfValidationIssue] = []
    unsearchable_pages: list[int] = []

    with pymupdf.open(pdf_path) as document:
        for page_index, page in enumerate(document):
            page_number = page_index + 1
            text = page.get_text("text")
            if not text.strip():
                unsearchable_pages.append(page_number)
                continue

            for label, pattern in rules:
                count = sum(1 for _ in pattern.finditer(text))
                if count:
                    issues.append(
                        PdfValidationIssue(
                            page_number=page_number,
                            label=label,
                            count=count,
                        )
                    )

    return PdfValidationReport(issues, unsearchable_pages)


def _compile_term(term: str) -> re.Pattern[str]:
    if term == NG_RULE_LABEL:
        return re.compile(
            r"(?<![A-Z0-9])N\s*\.?\s*G(?![A-Z0-9])",
            re.IGNORECASE,
        )
    if term == HASH_RULE_LABEL:
        return re.compile(r"(?<!#)##(?!#)")
    if term == EXCEL_HASH_RULE_LABEL:
        return re.compile(r"#{3,}")
    return re.compile(re.escape(term), re.IGNORECASE)

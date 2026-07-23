from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class ConversionStatus(StrEnum):
    WAITING = "대기"
    CONVERTING = "변환 중"
    SUCCESS = "성공"
    FAILED = "실패"
    SKIPPED = "건너뜀"


@dataclass(frozen=True, slots=True)
class PdfValidationIssue:
    page_number: int
    label: str
    count: int


@dataclass(frozen=True, slots=True)
class ExcelValidationIssue:
    sheet_name: str
    row: int
    column: int
    column_name: str
    address: str
    label: str


@dataclass(slots=True)
class ConversionItem:
    source_path: Path
    page_range: str = "전체"
    pdf_validation_enabled: bool = True
    excel_validation_enabled: bool = True
    status: ConversionStatus = ConversionStatus.WAITING
    output_path: Path | None = None
    error: str = ""
    validation_checked: bool = False
    validation_issues: list[PdfValidationIssue] = field(default_factory=list)
    excel_validation_issues: list[ExcelValidationIssue] = field(
        default_factory=list
    )
    validation_unsearchable_pages: list[int] = field(default_factory=list)
    validation_error: str = ""

    @property
    def filename(self) -> str:
        return self.source_path.name

    @property
    def extension(self) -> str:
        return self.source_path.suffix.lower().lstrip(".").upper()

    @property
    def validation_issue_count(self) -> int:
        return sum(issue.count for issue in self.validation_issues) + len(
            self.excel_validation_issues
        )

    @property
    def validation_summary(self) -> str:
        if not self.validation_checked:
            return "검사 안 함"
        details: list[str] = []
        for issue in self.excel_validation_issues:
            details.append(
                f"엑셀 [{issue.sheet_name}] {issue.row}행 "
                f"{issue.column_name}열({issue.address}): {issue.label}"
            )

        page_numbers = sorted({issue.page_number for issue in self.validation_issues})
        for page_number in page_numbers:
            page_issues = [
                f"{issue.label} {issue.count}건"
                for issue in self.validation_issues
                if issue.page_number == page_number
            ]
            details.append(f"{page_number}페이지: {', '.join(page_issues)}")

        if self.validation_unsearchable_pages:
            pages = _format_page_numbers(self.validation_unsearchable_pages)
            details.append(f"텍스트 검색 불가: {pages}페이지")
        if self.validation_error:
            details.append(f"검사 실패: {self.validation_error}")
        if not details:
            details.append("이상 없음")
        return " | ".join(details)


def _format_page_numbers(page_numbers: list[int]) -> str:
    numbers = sorted(set(page_numbers))
    if not numbers:
        return ""

    ranges: list[str] = []
    start = previous = numbers[0]
    for number in numbers[1:]:
        if number == previous + 1:
            previous = number
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = number
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ", ".join(ranges)

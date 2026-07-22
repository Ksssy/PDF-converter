from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from pypdf import PdfReader, PdfWriter

if TYPE_CHECKING:
    from pdf_converter.converters.base import ConversionOptions


class PageRangeError(ValueError):
    pass


def parse_page_range(expression: str, page_count: int) -> list[int]:
    """Return zero-based page indexes for a Korean-style page-range expression."""
    normalized = expression.strip().lower()
    if not normalized or normalized in {"전체", "all"}:
        return list(range(page_count))

    pages: set[int] = set()
    try:
        for token in normalized.replace(" ", "").split(","):
            if not token:
                raise PageRangeError("빈 페이지 항목이 있습니다.")
            if "-" in token:
                start_text, end_text = token.split("-", 1)
                start, end = int(start_text), int(end_text)
                if start > end:
                    raise PageRangeError(f"페이지 범위의 시작이 끝보다 큽니다: {token}")
                pages.update(range(start, end + 1))
            else:
                pages.add(int(token))
    except ValueError as error:
        if isinstance(error, PageRangeError):
            raise
        raise PageRangeError(f"페이지 범위를 확인해주세요: {expression}") from error

    if not pages or min(pages) < 1 or max(pages) > page_count:
        raise PageRangeError(
            f"페이지 범위는 1~{page_count} 사이여야 합니다: {expression}"
        )
    return [page - 1 for page in sorted(pages)]


def unique_output_path(output_directory: Path, source_stem: str) -> Path:
    candidate = output_directory / f"{source_stem}.pdf"
    sequence = 1
    while candidate.exists():
        candidate = output_directory / f"{source_stem} ({sequence}).pdf"
        sequence += 1
    return candidate


def finalize_exported_pdf(
    exported_pdf: Path,
    source: Path,
    options: ConversionOptions,
) -> Path:
    target = unique_output_path(options.output_directory, source.stem)
    reader = PdfReader(str(exported_pdf))
    selected_pages = parse_page_range(options.page_range, len(reader.pages))

    if len(selected_pages) == len(reader.pages):
        shutil.move(str(exported_pdf), target)
        return target

    writer = PdfWriter()
    for page_index in selected_pages:
        writer.add_page(reader.pages[page_index])
    with target.open("wb") as output_stream:
        writer.write(output_stream)
    return target

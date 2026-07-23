from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pymupdf
from pypdf import PdfReader

if TYPE_CHECKING:
    from pdf_converter.converters.base import ConversionOptions


class PageRangeError(ValueError):
    pass


IMAGE_COMPRESSION_SETTINGS = {
    "최소용량": {
        "dpi_threshold": 180,
        "dpi_target": 120,
        "quality": 70,
    },
    "일반": {
        "dpi_threshold": 360,
        "dpi_target": 220,
        "quality": 85,
    },
}


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

    needs_page_selection = len(selected_pages) != len(reader.pages)
    needs_grayscale = options.color_mode == "흑백"
    compression_settings = IMAGE_COMPRESSION_SETTINGS.get(options.quality)
    needs_image_compression = compression_settings is not None

    if not needs_page_selection and not needs_grayscale and not needs_image_compression:
        shutil.move(str(exported_pdf), target)
        return target

    with pymupdf.open(exported_pdf) as document:
        if needs_page_selection:
            document.select(selected_pages)
        if needs_grayscale:
            document.recolor(components=1)
        if needs_image_compression:
            document.rewrite_images(**compression_settings)
        document.save(target, garbage=4, deflate=True)
    return target

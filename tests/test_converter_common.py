from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from pdf_converter.converters.base import ConversionOptions
from pdf_converter.converters.common import (
    PageRangeError,
    finalize_exported_pdf,
    parse_page_range,
    unique_output_path,
)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("전체", [0, 1, 2, 3, 4]),
        ("", [0, 1, 2, 3, 4]),
        ("1", [0]),
        ("1,3-4", [0, 2, 3]),
        ("4,2,2", [1, 3]),
    ],
)
def test_parse_page_range(expression: str, expected: list[int]) -> None:
    assert parse_page_range(expression, 5) == expected


@pytest.mark.parametrize("expression", ["0", "6", "4-2", "1,,2", "abc"])
def test_parse_page_range_rejects_invalid_values(expression: str) -> None:
    with pytest.raises(PageRangeError):
        parse_page_range(expression, 5)


def test_unique_output_path_increments_existing_name(tmp_path: Path) -> None:
    (tmp_path / "문서.pdf").touch()
    (tmp_path / "문서 (1).pdf").touch()

    assert unique_output_path(tmp_path, "문서") == tmp_path / "문서 (2).pdf"


def test_finalize_exported_pdf_applies_page_range(tmp_path: Path) -> None:
    exported = tmp_path / "temporary.pdf"
    writer = PdfWriter()
    for _ in range(4):
        writer.add_blank_page(width=100, height=100)
    with exported.open("wb") as stream:
        writer.write(stream)

    output_directory = tmp_path / "output"
    output_directory.mkdir()
    result = finalize_exported_pdf(
        exported,
        tmp_path / "보고서.docx",
        ConversionOptions(output_directory=output_directory, page_range="2-3"),
    )

    assert result == output_directory / "보고서.pdf"
    assert len(PdfReader(str(result)).pages) == 2

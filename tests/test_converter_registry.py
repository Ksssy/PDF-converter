from pathlib import Path

import pytest

from pdf_converter.converters import (
    ExcelConverter,
    HwpConverter,
    PowerPointConverter,
    WordConverter,
    create_default_registry,
)


@pytest.mark.parametrize(
    ("filename", "converter_type"),
    [
        ("문서.docx", WordConverter),
        ("표.xlsx", ExcelConverter),
        ("발표.pptx", PowerPointConverter),
        ("한글문서.hwp", HwpConverter),
        ("한글문서.hwpx", HwpConverter),
    ],
)
def test_default_registry_resolves_office_files(filename: str, converter_type: type) -> None:
    converter = create_default_registry().resolve(Path(filename))
    assert isinstance(converter, converter_type)

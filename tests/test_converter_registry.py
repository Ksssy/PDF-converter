from pathlib import Path

import pytest

from pdf_converter.converters import (
    ExcelConverter,
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
    ],
)
def test_default_registry_resolves_office_files(filename: str, converter_type: type) -> None:
    converter = create_default_registry().resolve(Path(filename))
    assert isinstance(converter, converter_type)


def test_default_registry_rejects_hwp_until_converter_is_added() -> None:
    with pytest.raises(ValueError, match="지원하지 않는 파일 형식"):
        create_default_registry().resolve(Path("문서.hwp"))

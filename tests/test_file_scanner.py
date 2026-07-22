from pathlib import Path

from pdf_converter.services.file_scanner import is_supported


def test_supported_extension() -> None:
    assert is_supported(Path(__file__)) is False

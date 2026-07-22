from __future__ import annotations

from pathlib import Path

from pdf_converter.core.constants import SUPPORTED_EXTENSIONS, TEMP_PREFIXES


def is_supported(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and not path.name.startswith(TEMP_PREFIXES)
    )


def scan_folder(folder: Path, recursive: bool = True) -> list[Path]:
    iterator = folder.rglob("*") if recursive else folder.glob("*")
    return sorted((path for path in iterator if is_supported(path)), key=lambda p: str(p).lower())

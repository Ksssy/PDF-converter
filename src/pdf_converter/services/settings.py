from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(slots=True)
class AppSettings:
    output_directory: str = ""
    quality: str = "일반"
    color_mode: str = "컬러"
    include_subfolders: bool = True
    use_pdf_printer: bool = False
    printer_name: str = ""
    validate_ng: bool = True
    validate_hashes: bool = True
    validate_questions: bool = True
    custom_validation_terms: str = ""


class SettingsService:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path.home() / ".pdf_converter" / "config.json"

    def load(self) -> AppSettings:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return AppSettings(**data)
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(asdict(settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

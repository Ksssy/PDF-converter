from __future__ import annotations

from datetime import datetime
from pathlib import Path


class LoggingService:
    def __init__(self, log_dir: Path | None = None) -> None:
        self.log_dir = log_dir or Path.home() / ".pdf_converter" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def write(self, message: str) -> Path:
        path = self.log_dir / f"conversion_{datetime.now():%Y%m%d}.txt"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with path.open("a", encoding="utf-8") as stream:
            stream.write(f"[{timestamp}] {message}\n")
        return path

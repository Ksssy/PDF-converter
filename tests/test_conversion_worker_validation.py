from pathlib import Path

from pdf_converter.core.models import ConversionItem
from pdf_converter.services import conversion_worker as worker_module
from pdf_converter.services.conversion_worker import ConversionWorker
from pdf_converter.services.pdf_validation import PdfValidationReport


def test_worker_only_validates_files_with_enabled_checkbox(
    monkeypatch,
    tmp_path: Path,
) -> None:
    validation_calls: list[Path] = []

    class FakeConverter:
        def convert(self, source: Path, _options) -> Path:
            return tmp_path / f"{source.stem}.pdf"

    class FakeRegistry:
        def resolve(self, _source: Path) -> FakeConverter:
            return FakeConverter()

    class FakeLoggingService:
        def write(self, _message: str) -> Path:
            return tmp_path / "conversion.txt"

    def fake_inspect(pdf_path: Path, _terms: list[str]) -> PdfValidationReport:
        validation_calls.append(pdf_path)
        return PdfValidationReport([], [])

    monkeypatch.setattr(
        worker_module,
        "create_default_registry",
        lambda: FakeRegistry(),
    )
    monkeypatch.setattr(worker_module, "LoggingService", FakeLoggingService)
    monkeypatch.setattr(
        worker_module,
        "inspect_pdf_for_errors",
        fake_inspect,
    )

    checked = ConversionItem(
        tmp_path / "checked.xlsx",
        validation_enabled=True,
    )
    unchecked = ConversionItem(
        tmp_path / "unchecked.xlsx",
        validation_enabled=False,
    )
    worker = ConversionWorker(
        [checked, unchecked],
        tmp_path,
        "일반",
        "컬러",
        validation_terms=["NG / N.G"],
    )

    worker.run()

    assert validation_calls == [tmp_path / "checked.pdf"]
    assert checked.validation_checked
    assert not unchecked.validation_checked

from pathlib import Path

from pdf_converter.core.models import ConversionItem, ExcelValidationIssue
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
        pdf_validation_enabled=True,
    )
    unchecked = ConversionItem(
        tmp_path / "unchecked.xlsx",
        pdf_validation_enabled=False,
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


def test_worker_inspects_source_excel_and_records_cell_locations(
    monkeypatch,
    tmp_path: Path,
) -> None:
    operation_order: list[str] = []

    class FakeConverter:
        def convert(self, source: Path, _options) -> Path:
            operation_order.append(f"convert:{source.name}")
            return tmp_path / f"{source.stem}.pdf"

    class FakeRegistry:
        def resolve(self, _source: Path) -> FakeConverter:
            return FakeConverter()

    class FakeLoggingService:
        def write(self, _message: str) -> Path:
            return tmp_path / "conversion.txt"

    def fake_excel_inspect(source: Path) -> list[ExcelValidationIssue]:
        operation_order.append(f"excel:{source.name}")
        return [
            ExcelValidationIssue(
                sheet_name="수량",
                row=8,
                column=3,
                column_name="C",
                address="C8",
                label="#N/A",
            )
        ]

    monkeypatch.setattr(
        worker_module,
        "create_default_registry",
        lambda: FakeRegistry(),
    )
    monkeypatch.setattr(worker_module, "LoggingService", FakeLoggingService)
    monkeypatch.setattr(
        worker_module,
        "inspect_excel_for_errors",
        fake_excel_inspect,
    )

    item = ConversionItem(tmp_path / "quantity.xlsx")
    worker = ConversionWorker(
        [item],
        tmp_path,
        "일반",
        "컬러",
        validate_excel_errors=True,
    )

    worker.run()

    assert operation_order == ["excel:quantity.xlsx", "convert:quantity.xlsx"]
    assert item.validation_checked
    assert item.validation_summary == "엑셀 [수량] 8행 C열(C8): #N/A"


def test_worker_keeps_pdf_and_excel_validation_independent(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    class FakeConverter:
        def convert(self, source: Path, _options) -> Path:
            return tmp_path / f"{source.stem}.pdf"

    class FakeRegistry:
        def resolve(self, _source: Path) -> FakeConverter:
            return FakeConverter()

    class FakeLoggingService:
        def write(self, _message: str) -> Path:
            return tmp_path / "conversion.txt"

    def fake_excel_inspect(_source: Path) -> list[ExcelValidationIssue]:
        calls.append("excel")
        return []

    def fake_pdf_inspect(
        _pdf_path: Path,
        _terms: list[str],
    ) -> PdfValidationReport:
        calls.append("pdf")
        return PdfValidationReport([], [])

    monkeypatch.setattr(worker_module, "create_default_registry", lambda: FakeRegistry())
    monkeypatch.setattr(worker_module, "LoggingService", FakeLoggingService)
    monkeypatch.setattr(worker_module, "inspect_excel_for_errors", fake_excel_inspect)
    monkeypatch.setattr(worker_module, "inspect_pdf_for_errors", fake_pdf_inspect)

    excel_only = ConversionItem(
        tmp_path / "excel-only.xlsx",
        pdf_validation_enabled=False,
        excel_validation_enabled=True,
    )
    pdf_only = ConversionItem(
        tmp_path / "pdf-only.xlsx",
        pdf_validation_enabled=True,
        excel_validation_enabled=False,
    )
    worker = ConversionWorker(
        [excel_only, pdf_only],
        tmp_path,
        "일반",
        "컬러",
        validation_terms=["NG / N.G"],
        validate_excel_errors=True,
    )

    worker.run()

    assert calls == ["excel", "pdf"]
    assert excel_only.validation_checked
    assert pdf_only.validation_checked

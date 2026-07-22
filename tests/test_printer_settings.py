from pathlib import Path

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QApplication

from pdf_converter.converters.common import IMAGE_COMPRESSION_SETTINGS
from pdf_converter.gui import main_window as main_window_module
from pdf_converter.gui.main_window import MainWindow
from pdf_converter.services import printer_service
from pdf_converter.services.printer_service import _fit_rect
from pdf_converter.services.printer_service import print_pdf_with_printer
from pdf_converter.services.settings import AppSettings, SettingsService


def test_quality_settings_have_distinct_image_targets() -> None:
    assert IMAGE_COMPRESSION_SETTINGS["최소용량"]["dpi_target"] == 120
    assert IMAGE_COMPRESSION_SETTINGS["일반"]["dpi_target"] == 220
    assert "고품질" not in IMAGE_COMPRESSION_SETTINGS


def test_settings_round_trip_printer_selection(tmp_path: Path) -> None:
    service = SettingsService(tmp_path / "settings.json")
    expected = AppSettings(
        use_pdf_printer=True,
        printer_name="My PDF Printer",
        validate_excel_errors=False,
    )

    service.save(expected)

    assert service.load() == expected


def test_main_window_only_detects_printers_when_button_is_used(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls = 0

    def fake_list_installed_printers() -> list[str]:
        nonlocal calls
        calls += 1
        return ["Office PDF", "Windows PDF"]

    monkeypatch.setattr(
        main_window_module,
        "list_installed_printers",
        fake_list_installed_printers,
    )
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.settings_service.path = tmp_path / "settings.json"

    assert calls == 0
    assert window.printer_combo.count() <= 1

    window.refresh_printers()

    assert calls == 1
    assert [window.printer_combo.itemText(index) for index in range(2)] == [
        "Office PDF",
        "Windows PDF",
    ]
    window.close()
    app.processEvents()


def test_fit_rect_keeps_page_aspect_ratio() -> None:
    fitted = _fit_rect(QRectF(0, 0, 1000, 1000), width=500, height=1000)

    assert fitted.width() == 500
    assert fitted.height() == 1000
    assert fitted.x() == 250


def test_missing_saved_printer_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-invalid-for-printer-name-test")

    try:
        print_pdf_with_printer(source, "Definitely Missing Printer", "일반")
    except RuntimeError as error:
        assert "프린터 인식 버튼을 다시 눌러주세요" in str(error)
    else:
        raise AssertionError("A missing printer must not fall back to the default printer")


def test_printer_properties_opens_selected_driver(monkeypatch) -> None:
    captured: list[str] = []

    def fake_run(command, **_kwargs):
        captured.extend(command)

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(printer_service, "printer_exists", lambda _name: True)
    monkeypatch.setattr(printer_service.subprocess, "run", fake_run)

    printer_service.open_printer_properties("Office PDF")

    assert captured == [
        "rundll32.exe",
        "printui.dll,PrintUIEntry",
        "/e",
        "/n",
        "Office PDF",
    ]

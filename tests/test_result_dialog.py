from pathlib import Path

from PySide6.QtWidgets import QApplication

from pdf_converter.core.models import (
    ConversionItem,
    ConversionStatus,
    PdfValidationIssue,
)
from pdf_converter.gui.result_dialog import ResultDialog


def test_result_dialog_lists_success_and_failure(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    output_directory = tmp_path / "output"
    output_directory.mkdir()
    log_path = tmp_path / "conversion.txt"
    log_path.write_text("test", encoding="utf-8")

    success = ConversionItem(
        tmp_path / "success.docx",
        status=ConversionStatus.SUCCESS,
        output_path=output_directory / "success.pdf",
        validation_checked=True,
        validation_issues=[PdfValidationIssue(2, "NG / N.G", 1)],
    )
    failure = ConversionItem(
        tmp_path / "failure.hwp",
        status=ConversionStatus.FAILED,
        error="변환 오류",
    )

    dialog = ResultDialog(
        [success, failure],
        success_count=1,
        failure_count=1,
        skipped_count=0,
        output_directory=output_directory,
        log_path=log_path,
    )

    assert "성공 1개" in dialog.summary_label.text()
    assert "실패 1개" in dialog.summary_label.text()
    assert dialog.table.rowCount() == 2
    assert dialog.table.item(0, 3).text().endswith("success.pdf")
    assert dialog.table.item(0, 4).text() == "2페이지: NG / N.G 1건"
    assert dialog.table.item(1, 5).text() == "변환 오류"
    assert "PDF 오류 발견 1개 파일, 1건" in dialog.summary_label.text()
    dialog.table.setCurrentCell(0, 4)
    dialog.copy_validation_result()
    assert QApplication.clipboard().text() == "2페이지: NG / N.G 1건"
    assert dialog.output_button.isEnabled()
    assert dialog.log_button.isEnabled()
    dialog.close()
    app.processEvents()

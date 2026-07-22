from pathlib import Path

from PySide6.QtWidgets import QApplication

from pdf_converter.gui.main_window import (
    COL_FILENAME,
    COL_SOURCE_PATH,
    MainWindow,
)


def test_table_allows_filename_path_editing_and_copy(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "original.xlsx"
    source.touch()
    replacement = tmp_path / "replacement.docx"
    replacement.touch()

    window = MainWindow()
    window.settings_service.path = tmp_path / "settings.json"
    window._add_paths([source])

    window.table.item(0, COL_FILENAME).setText("renamed.xlsx")
    assert window.items[0].source_path == tmp_path / "renamed.xlsx"

    window.table.item(0, COL_SOURCE_PATH).setText(str(replacement))
    assert window.items[0].source_path == replacement
    assert window.table.item(0, COL_FILENAME).text() == "replacement.docx"

    window.table.setCurrentCell(0, COL_SOURCE_PATH)
    window.copy_current_source_path()
    assert QApplication.clipboard().text() == str(replacement)

    window.close()
    app.processEvents()

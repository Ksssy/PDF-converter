from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from pdf_converter.gui import main_window as main_window_module
from pdf_converter.gui.main_window import (
    COL_FILENAME,
    COL_SOURCE_PATH,
    COL_VALIDATION_ENABLED,
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

    assert window.items[0].validation_enabled
    window.table.item(0, COL_VALIDATION_ENABLED).setCheckState(
        Qt.CheckState.Unchecked
    )
    assert not window.items[0].validation_enabled

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


def test_file_and_folder_dialogs_share_last_session_location(
    monkeypatch,
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    file_directory = tmp_path / "documents"
    file_directory.mkdir()
    source = file_directory / "calculation.xlsx"
    source.touch()
    selected_folder = tmp_path / "project-folder"
    selected_folder.mkdir()

    file_start_directories: list[str] = []
    folder_start_directories: list[str] = []
    file_responses = [([str(source)], ""), ([], "")]

    def fake_get_open_file_names(_parent, _title, directory):
        file_start_directories.append(directory)
        return file_responses.pop(0)

    def fake_get_existing_directory(_parent, _title, directory):
        folder_start_directories.append(directory)
        return str(selected_folder)

    monkeypatch.setattr(
        main_window_module.QFileDialog,
        "getOpenFileNames",
        fake_get_open_file_names,
    )
    monkeypatch.setattr(
        main_window_module.QFileDialog,
        "getExistingDirectory",
        fake_get_existing_directory,
    )

    window = MainWindow()
    window.settings_service.path = tmp_path / "settings.json"
    window.last_browse_directory = tmp_path

    window.add_files()
    window.add_folder()
    window.add_files()

    assert file_start_directories == [str(tmp_path), str(selected_folder)]
    assert folder_start_directories == [str(file_directory)]
    assert window.last_browse_directory == selected_folder

    window.close()
    app.processEvents()

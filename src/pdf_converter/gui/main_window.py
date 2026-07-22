from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pdf_converter import __version__
from pdf_converter.core.models import ConversionItem, ConversionStatus
from pdf_converter.gui.result_dialog import ResultDialog
from pdf_converter.services.conversion_worker import ConversionWorker
from pdf_converter.services.file_scanner import is_supported, scan_folder
from pdf_converter.services.settings import AppSettings, SettingsService


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"PDF변환기 v{__version__}")
        self.resize(1100, 700)
        self.setAcceptDrops(True)

        self.settings_service = SettingsService()
        self.settings = self.settings_service.load()
        self.items: list[ConversionItem] = []
        self.conversion_thread: QThread | None = None
        self.conversion_worker: ConversionWorker | None = None
        self.is_paused = False

        self._build_ui()
        self._restore_settings()

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        toolbar = QHBoxLayout()
        self.file_action_buttons: list[QPushButton] = []
        for label, handler in (
            ("파일 추가", self.add_files),
            ("폴더 추가", self.add_folder),
            ("선택 삭제", self.remove_selected),
            ("전체 삭제", self.clear_all),
            ("위로", self.move_up),
            ("아래로", self.move_down),
        ):
            button = QPushButton(label)
            button.clicked.connect(handler)
            self.file_action_buttons.append(button)
            toolbar.addWidget(button)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["순번", "파일명", "파일형식", "페이지 범위", "상태", "원본 경로"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 55)
        self.table.setColumnWidth(1, 260)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 150)
        self.table.setColumnWidth(4, 100)
        layout.addWidget(self.table)

        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("저장 폴더"))
        self.output_edit = QLineEdit()
        output_layout.addWidget(self.output_edit)
        browse = QPushButton("찾기")
        browse.clicked.connect(self.choose_output_folder)
        output_layout.addWidget(browse)
        layout.addLayout(output_layout)

        options = QHBoxLayout()
        options.addWidget(QLabel("PDF 품질"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["일반", "고품질", "최소용량"])
        options.addWidget(self.quality_combo)
        options.addSpacing(25)
        options.addWidget(QLabel("색상"))
        self.color_combo = QComboBox()
        self.color_combo.addItems(["컬러", "흑백"])
        options.addWidget(self.color_combo)
        options.addStretch()
        layout.addLayout(options)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        actions = QHBoxLayout()
        actions.addStretch()
        self.start_button = QPushButton("변환 시작")
        self.start_button.clicked.connect(self.start_conversion)
        actions.addWidget(self.start_button)

        self.pause_button = QPushButton("일시정지")
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self.toggle_pause)
        actions.addWidget(self.pause_button)

        self.stop_button = QPushButton("변환 중지")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_conversion)
        actions.addWidget(self.stop_button)
        layout.addLayout(actions)

        self.statusBar().showMessage("준비")

    def _restore_settings(self) -> None:
        self.output_edit.setText(self.settings.output_directory)
        self.quality_combo.setCurrentText(self.settings.quality)
        self.color_combo.setCurrentText(self.settings.color_mode)

    def add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "변환할 파일 선택")
        self._add_paths(Path(path) for path in paths)

    def add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "폴더 선택")
        if folder:
            self._add_paths(scan_folder(Path(folder), recursive=True))

    def _add_paths(self, paths) -> None:
        existing = {item.source_path.resolve() for item in self.items}
        for path in paths:
            path = Path(path)
            if is_supported(path) and path.resolve() not in existing:
                self.items.append(ConversionItem(path))
                existing.add(path.resolve())
        self._refresh_table()

    def _refresh_table(self) -> None:
        self.table.setRowCount(len(self.items))
        for row, item in enumerate(self.items):
            values = [str(row + 1), item.filename, item.extension, item.page_range, item.status.value, str(item.source_path)]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column != 3:
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, column, cell)
        self.statusBar().showMessage(f"파일 {len(self.items)}개")

    def _sync_page_ranges(self) -> None:
        for row, item in enumerate(self.items):
            cell = self.table.item(row, 3)
            if cell:
                item.page_range = cell.text().strip() or "전체"

    def remove_selected(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.items.pop(row)
        self._refresh_table()

    def clear_all(self) -> None:
        self.items.clear()
        self._refresh_table()

    def move_up(self) -> None:
        row = self.table.currentRow()
        if row > 0:
            self._sync_page_ranges()
            self.items[row - 1], self.items[row] = self.items[row], self.items[row - 1]
            self._refresh_table()
            self.table.selectRow(row - 1)

    def move_down(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self.items) - 1:
            self._sync_page_ranges()
            self.items[row + 1], self.items[row] = self.items[row], self.items[row + 1]
            self._refresh_table()
            self.table.selectRow(row + 1)

    def choose_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "PDF 저장 폴더 선택", self.output_edit.text())
        if folder:
            self.output_edit.setText(folder)

    def start_conversion(self) -> None:
        self._sync_page_ranges()
        if not self.items:
            QMessageBox.warning(self, "확인", "변환할 파일을 추가해주세요.")
            return
        output_text = self.output_edit.text().strip()
        if not output_text:
            QMessageBox.warning(self, "확인", "PDF 저장 폴더를 선택해주세요.")
            return

        output_directory = Path(output_text)
        try:
            output_directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            QMessageBox.critical(self, "저장 폴더 오류", str(error))
            return

        for item in self.items:
            item.status = ConversionStatus.WAITING
            item.output_path = None
            item.error = ""
        self._refresh_table()

        self.conversion_thread = QThread(self)
        self.conversion_worker = ConversionWorker(
            list(self.items),
            output_directory,
            self.quality_combo.currentText(),
            self.color_combo.currentText(),
        )
        self.conversion_worker.moveToThread(self.conversion_thread)
        self.conversion_thread.started.connect(self.conversion_worker.run)
        self.conversion_worker.item_started.connect(self._on_item_started)
        self.conversion_worker.item_succeeded.connect(self._on_item_succeeded)
        self.conversion_worker.item_failed.connect(self._on_item_failed)
        self.conversion_worker.item_skipped.connect(self._on_item_skipped)
        self.conversion_worker.progress_changed.connect(self.progress.setValue)
        self.conversion_worker.completed.connect(self.conversion_worker.deleteLater)
        self.conversion_worker.completed.connect(self.conversion_thread.quit)
        self.conversion_worker.completed.connect(self._on_conversion_completed)
        self.conversion_thread.finished.connect(self.conversion_thread.deleteLater)
        self.conversion_thread.finished.connect(self._cleanup_conversion)

        self.progress.setValue(0)
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self._set_inputs_enabled(False)
        self.statusBar().showMessage("변환 중")
        self.conversion_thread.start()

    def toggle_pause(self) -> None:
        if self.conversion_worker is None:
            return
        self.is_paused = not self.is_paused
        self.conversion_worker.set_paused(self.is_paused)
        self.pause_button.setText("계속" if self.is_paused else "일시정지")
        self.statusBar().showMessage("일시정지" if self.is_paused else "변환 중")

    def stop_conversion(self) -> None:
        if self.conversion_worker is not None:
            self.conversion_worker.request_stop()
            self.statusBar().showMessage("중지 요청 중")
            self.pause_button.setEnabled(False)
            self.stop_button.setEnabled(False)

    def _update_item_status(self, index: int, status: ConversionStatus) -> None:
        if 0 <= index < len(self.items):
            self.items[index].status = status
            self._refresh_table()

    def _on_item_started(self, index: int) -> None:
        self._update_item_status(index, ConversionStatus.CONVERTING)

    def _on_item_succeeded(self, index: int, output_path: str) -> None:
        self.items[index].output_path = Path(output_path)
        self._update_item_status(index, ConversionStatus.SUCCESS)

    def _on_item_failed(self, index: int, error: str) -> None:
        self.items[index].error = error
        self._update_item_status(index, ConversionStatus.FAILED)

    def _on_item_skipped(self, index: int) -> None:
        self._update_item_status(index, ConversionStatus.SKIPPED)

    def _on_conversion_completed(
        self,
        success_count: int,
        failure_count: int,
        skipped_count: int,
        log_path: str,
    ) -> None:
        self.statusBar().showMessage("변환 완료")
        dialog = ResultDialog(
            list(self.items),
            success_count,
            failure_count,
            skipped_count,
            Path(self.output_edit.text().strip()),
            Path(log_path),
            self,
        )
        dialog.exec()

    def _cleanup_conversion(self) -> None:
        self.conversion_worker = None
        self.conversion_thread = None
        self.is_paused = False
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.pause_button.setText("일시정지")
        self.stop_button.setEnabled(False)
        self._set_inputs_enabled(True)

    def _set_inputs_enabled(self, enabled: bool) -> None:
        for button in self.file_action_buttons:
            button.setEnabled(enabled)
        self.table.setEnabled(enabled)
        self.output_edit.setEnabled(enabled)
        self.quality_combo.setEnabled(enabled)
        self.color_combo.setEnabled(enabled)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths: list[Path] = []
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_dir():
                paths.extend(scan_folder(path, recursive=True))
            else:
                paths.append(path)
        self._add_paths(paths)
        event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.conversion_thread is not None and self.conversion_thread.isRunning():
            QMessageBox.warning(self, "변환 중", "변환을 중지한 뒤 프로그램을 종료해주세요.")
            event.ignore()
            return
        self.settings_service.save(
            AppSettings(
                output_directory=self.output_edit.text().strip(),
                quality=self.quality_combo.currentText(),
                color_mode=self.color_combo.currentText(),
                include_subfolders=True,
            )
        )
        event.accept()

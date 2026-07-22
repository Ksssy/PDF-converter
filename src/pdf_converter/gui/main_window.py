from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
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

from pdf_converter.core.models import ConversionItem
from pdf_converter.services.file_scanner import is_supported, scan_folder
from pdf_converter.services.settings import AppSettings, SettingsService


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PDF변환기")
        self.resize(1100, 700)
        self.setAcceptDrops(True)

        self.settings_service = SettingsService()
        self.settings = self.settings_service.load()
        self.items: list[ConversionItem] = []

        self._build_ui()
        self._restore_settings()

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        toolbar = QHBoxLayout()
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
        for label, enabled in (("변환 시작", True), ("일시정지", False), ("변환 중지", False)):
            button = QPushButton(label)
            button.setEnabled(enabled)
            if label == "변환 시작":
                button.clicked.connect(self.start_conversion_placeholder)
            actions.addWidget(button)
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

    def start_conversion_placeholder(self) -> None:
        self._sync_page_ranges()
        if not self.items:
            QMessageBox.warning(self, "확인", "변환할 파일을 추가해주세요.")
            return
        if not self.output_edit.text().strip():
            QMessageBox.warning(self, "확인", "PDF 저장 폴더를 선택해주세요.")
            return
        QMessageBox.information(
            self,
            "1차 개발 상태",
            "GUI와 파일 관리 기반이 완성되었습니다.\n다음 단계에서 Excel/Word COM 변환 엔진을 연결합니다.",
        )

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
        self.settings_service.save(
            AppSettings(
                output_directory=self.output_edit.text().strip(),
                quality=self.quality_combo.currentText(),
                color_mode=self.color_combo.currentText(),
                include_subfolders=True,
            )
        )
        event.accept()

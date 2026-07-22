from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QThread, Qt
from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
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
from pdf_converter.services.excel_validation import (
    EXCEL_ERROR_HELP_TEXT,
    EXCEL_FAST_HELP_TEXT,
    EXCEL_PRECISE_HELP_TEXT,
    EXCEL_SCOPE_HELP_TEXT,
    EXCEL_VALIDATION_FAST,
    EXCEL_VALIDATION_PRECISE,
    is_excel_source,
)
from pdf_converter.services.file_scanner import is_supported, scan_folder
from pdf_converter.services.pdf_validation import build_validation_terms
from pdf_converter.services.printer_service import (
    list_installed_printers,
    open_printer_properties,
)
from pdf_converter.services.settings import AppSettings, SettingsService


QUALITY_DESCRIPTIONS = {
    "최소용량": "120DPI 중심으로 이미지를 강하게 압축합니다. 이메일·보관용에 적합합니다.",
    "일반": "220DPI 중심으로 용량과 선명도의 균형을 맞춥니다. 일반 문서용입니다.",
    "고품질": "이미지를 추가 압축하지 않습니다. 도면·사진·확대 인쇄용입니다.",
}

PRINTER_QUALITY_DESCRIPTIONS = {
    "최소용량": "선택한 프린터에 200DPI로 출력합니다. 용량을 줄일 때 사용합니다.",
    "일반": "선택한 프린터에 300DPI로 출력합니다. 일반 인쇄 품질입니다.",
    "고품질": "선택한 프린터에 450DPI로 출력합니다. 도면·확대 출력용입니다.",
}

COL_NUMBER = 0
COL_PDF_VALIDATION_ENABLED = 1
COL_EXCEL_VALIDATION_ENABLED = 2
COL_FILENAME = 3
COL_EXTENSION = 4
COL_PAGE_RANGE = 5
COL_STATUS = 6
COL_VALIDATION = 7
COL_SOURCE_PATH = 8
EDITABLE_COLUMNS = {COL_FILENAME, COL_PAGE_RANGE, COL_SOURCE_PATH}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"PDF변환기 v{__version__}")
        self.resize(1220, 790)
        self.setAcceptDrops(True)

        self.settings_service = SettingsService()
        self.settings = self.settings_service.load()
        self.items: list[ConversionItem] = []
        self.conversion_thread: QThread | None = None
        self.conversion_worker: ConversionWorker | None = None
        self.is_paused = False
        self.last_browse_directory = Path.home()

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

        table_help = QLabel(
            "파일별 PDF 검사와 Excel 검사를 각각 선택하고, 파일명·페이지 범위·"
            "원본 경로는 직접 수정할 수 있습니다. 우클릭하면 복사 메뉴가 열립니다."
        )
        table_help.setStyleSheet("color: #555;")
        layout.addWidget(table_help)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "순번",
                "PDF 검사",
                "Excel 검사",
                "파일명",
                "파일형식",
                "페이지 범위",
                "상태",
                "오류 검사 결과",
                "원본 경로",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(
            self._show_table_context_menu
        )
        self.table.itemChanged.connect(self._on_table_item_changed)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(COL_NUMBER, 55)
        self.table.setColumnWidth(COL_PDF_VALIDATION_ENABLED, 80)
        self.table.setColumnWidth(COL_EXCEL_VALIDATION_ENABLED, 85)
        self.table.setColumnWidth(COL_FILENAME, 210)
        self.table.setColumnWidth(COL_EXTENSION, 80)
        self.table.setColumnWidth(COL_PAGE_RANGE, 120)
        self.table.setColumnWidth(COL_STATUS, 90)
        self.table.setColumnWidth(COL_VALIDATION, 280)
        layout.addWidget(self.table)

        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("저장 폴더"))
        self.output_edit = QLineEdit()
        output_layout.addWidget(self.output_edit)
        self.output_browse_button = QPushButton("찾기")
        self.output_browse_button.clicked.connect(self.choose_output_folder)
        output_layout.addWidget(self.output_browse_button)
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

        self.quality_description = QLabel()
        self.quality_description.setStyleSheet("color: #666;")
        self.quality_combo.currentTextChanged.connect(self._update_quality_description)
        layout.addWidget(self.quality_description)

        printer_layout = QHBoxLayout()
        printer_layout.addWidget(QLabel("PDF 출력 방식"))
        self.output_method_combo = QComboBox()
        self.output_method_combo.addItem("내장 PDF 엔진 (권장)", False)
        self.output_method_combo.addItem("선택한 PDF 프린터 사용", True)
        self.output_method_combo.currentIndexChanged.connect(
            self._update_printer_controls
        )
        printer_layout.addWidget(self.output_method_combo)

        printer_layout.addSpacing(15)
        printer_layout.addWidget(QLabel("프린터"))
        self.printer_combo = QComboBox()
        self.printer_combo.setMinimumWidth(300)
        self.printer_combo.setPlaceholderText("프린터 인식 버튼을 누르세요")
        self.printer_combo.setToolTip(
            "PDF를 파일로 저장할 수 있는 가상 프린터를 선택해주세요."
        )
        printer_layout.addWidget(self.printer_combo)

        self.detect_printers_button = QPushButton("프린터 인식")
        self.detect_printers_button.clicked.connect(self.refresh_printers)
        printer_layout.addWidget(self.detect_printers_button)

        self.printer_properties_button = QPushButton("프린터 속성")
        self.printer_properties_button.setToolTip(
            "선택한 프린터 드라이버의 인쇄 기본 설정을 엽니다."
        )
        self.printer_properties_button.clicked.connect(
            self.show_printer_properties
        )
        printer_layout.addWidget(self.printer_properties_button)
        self.printer_combo.currentTextChanged.connect(
            self._update_printer_controls
        )
        printer_layout.addStretch()
        layout.addLayout(printer_layout)

        self.printer_note = QLabel(
            "프린터 방식은 PDF 가상 프린터 전용입니다. "
            "드라이버 특성에 따라 텍스트 검색이 지원되지 않을 수 있습니다."
        )
        self.printer_note.setStyleSheet("color: #9a5b00;")
        layout.addWidget(self.printer_note)

        validation_layout = QHBoxLayout()
        validation_layout.addWidget(QLabel("PDF 오류 검사"))
        self.validate_ng_checkbox = QCheckBox("NG / N.G")
        self.validate_hashes_checkbox = QCheckBox("##")
        self.validate_questions_checkbox = QCheckBox("??")
        validation_layout.addWidget(self.validate_ng_checkbox)
        validation_layout.addWidget(self.validate_hashes_checkbox)
        validation_layout.addWidget(self.validate_questions_checkbox)
        validation_layout.addSpacing(15)
        validation_layout.addWidget(QLabel("직접 입력"))
        self.custom_validation_edit = QLineEdit()
        self.custom_validation_edit.setPlaceholderText(
            "쉼표로 구분: ERROR, WARNING, 미검토"
        )
        self.custom_validation_edit.setToolTip(
            "추가로 찾을 문구를 쉼표, 세미콜론 또는 줄바꿈으로 구분하세요."
        )
        validation_layout.addWidget(self.custom_validation_edit)
        validation_layout.addSpacing(20)
        validation_layout.addWidget(QLabel("Excel 오류 검사"))
        self.validate_excel_fast_checkbox = QCheckBox("빠른 검사")
        self.validate_excel_fast_checkbox.setToolTip(EXCEL_FAST_HELP_TEXT)
        self.validate_excel_precise_checkbox = QCheckBox("정밀 검사")
        self.validate_excel_precise_checkbox.setToolTip(
            EXCEL_PRECISE_HELP_TEXT
        )
        self.validate_excel_fast_checkbox.toggled.connect(
            self._on_excel_fast_toggled
        )
        self.validate_excel_precise_checkbox.toggled.connect(
            self._on_excel_precise_toggled
        )
        validation_layout.addWidget(self.validate_excel_fast_checkbox)
        validation_layout.addWidget(self.validate_excel_precise_checkbox)
        layout.addLayout(validation_layout)

        self.excel_error_help = QLabel(EXCEL_ERROR_HELP_TEXT)
        self.excel_error_help.setWordWrap(True)
        self.excel_error_help.setStyleSheet("color: #7a3e00;")
        layout.addWidget(self.excel_error_help)

        self.excel_mode_help = QLabel(
            f"{EXCEL_FAST_HELP_TEXT}  {EXCEL_PRECISE_HELP_TEXT}"
        )
        self.excel_mode_help.setWordWrap(True)
        self.excel_mode_help.setStyleSheet("color: #555;")
        layout.addWidget(self.excel_mode_help)

        self.excel_scope_help = QLabel(EXCEL_SCOPE_HELP_TEXT)
        self.excel_scope_help.setWordWrap(True)
        self.excel_scope_help.setStyleSheet("color: #555;")
        layout.addWidget(self.excel_scope_help)

        self.validation_note = QLabel(
            "파일별 PDF 검사와 Excel 검사를 독립적으로 선택합니다. "
            "엑셀 주요 오류는 원본 Excel의 시트·행·열을 검사합니다. "
            "나머지 오류 항목은 PDF 페이지별로 검사합니다. "
            "프린터 사용 시에는 텍스트가 그림으로 바뀌기 전에 검사합니다."
        )
        self.validation_note.setStyleSheet("color: #555;")
        layout.addWidget(self.validation_note)

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
        method_index = self.output_method_combo.findData(
            self.settings.use_pdf_printer
        )
        if method_index >= 0:
            self.output_method_combo.setCurrentIndex(method_index)
        if self.settings.printer_name:
            self.printer_combo.addItem(self.settings.printer_name)
            self.printer_combo.setCurrentText(self.settings.printer_name)
        self.validate_ng_checkbox.setChecked(self.settings.validate_ng)
        self.validate_hashes_checkbox.setChecked(self.settings.validate_hashes)
        self.validate_questions_checkbox.setChecked(
            self.settings.validate_questions
        )
        excel_mode = self.settings.excel_validation_mode
        if excel_mode not in {
            EXCEL_VALIDATION_FAST,
            EXCEL_VALIDATION_PRECISE,
        }:
            excel_mode = (
                EXCEL_VALIDATION_FAST
                if self.settings.validate_excel_errors
                else ""
            )
        self.validate_excel_fast_checkbox.setChecked(
            excel_mode == EXCEL_VALIDATION_FAST
        )
        self.validate_excel_precise_checkbox.setChecked(
            excel_mode == EXCEL_VALIDATION_PRECISE
        )
        self.custom_validation_edit.setText(
            self.settings.custom_validation_terms
        )
        self._update_quality_description(self.quality_combo.currentText())
        self._update_printer_controls()

    def _update_quality_description(self, quality: str) -> None:
        descriptions = (
            PRINTER_QUALITY_DESCRIPTIONS
            if bool(self.output_method_combo.currentData())
            else QUALITY_DESCRIPTIONS
        )
        self.quality_description.setText(descriptions.get(quality, ""))

    def _on_excel_fast_toggled(self, checked: bool) -> None:
        if checked:
            self.validate_excel_precise_checkbox.setChecked(False)

    def _on_excel_precise_toggled(self, checked: bool) -> None:
        if checked:
            self.validate_excel_fast_checkbox.setChecked(False)

    def _selected_excel_validation_mode(self) -> str:
        if self.validate_excel_precise_checkbox.isChecked():
            return EXCEL_VALIDATION_PRECISE
        if self.validate_excel_fast_checkbox.isChecked():
            return EXCEL_VALIDATION_FAST
        return ""

    def _update_printer_controls(
        self,
        _value: int | str | None = None,
    ) -> None:
        use_printer = bool(self.output_method_combo.currentData())
        self.printer_combo.setEnabled(use_printer)
        self.detect_printers_button.setEnabled(use_printer)
        self.printer_properties_button.setEnabled(
            use_printer and bool(self.printer_combo.currentText().strip())
        )
        self.printer_note.setVisible(use_printer)
        self._update_quality_description(self.quality_combo.currentText())

    def refresh_printers(self) -> None:
        current_name = self.printer_combo.currentText().strip()
        printer_names = list_installed_printers()
        self.printer_combo.clear()
        self.printer_combo.addItems(printer_names)
        if current_name in printer_names:
            self.printer_combo.setCurrentText(current_name)
        elif self.settings.printer_name in printer_names:
            self.printer_combo.setCurrentText(self.settings.printer_name)

        if printer_names:
            self.statusBar().showMessage(
                f"설치된 프린터 {len(printer_names)}개를 인식했습니다."
            )
        else:
            QMessageBox.warning(
                self,
                "프린터 인식",
                "Windows에 설치된 프린터를 찾지 못했습니다.",
            )

        self._update_printer_controls()

    def show_printer_properties(self) -> None:
        printer_name = self.printer_combo.currentText().strip()
        if not printer_name:
            QMessageBox.warning(
                self,
                "프린터 속성",
                "프린터 인식 버튼을 누르고 프린터를 선택해주세요.",
            )
            return
        try:
            open_printer_properties(printer_name)
        except RuntimeError as error:
            QMessageBox.critical(self, "프린터 속성", str(error))
        else:
            self.statusBar().showMessage(
                f"{printer_name} 드라이버 설정을 적용했습니다."
            )

    def add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "변환할 파일 선택",
            str(self.last_browse_directory),
        )
        if paths:
            self.last_browse_directory = Path(paths[0]).parent
        self._add_paths(Path(path) for path in paths)

    def add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "폴더 선택",
            str(self.last_browse_directory),
        )
        if folder:
            selected_folder = Path(folder)
            self.last_browse_directory = selected_folder
            self._add_paths(scan_folder(selected_folder, recursive=True))

    def _add_paths(self, paths) -> None:
        existing = {item.source_path.resolve() for item in self.items}
        for path in paths:
            path = Path(path)
            if is_supported(path) and path.resolve() not in existing:
                self.items.append(
                    ConversionItem(
                        path,
                        excel_validation_enabled=is_excel_source(path),
                    )
                )
                existing.add(path.resolve())
        self._refresh_table()

    def _refresh_table(self) -> None:
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.items))
            for row, item in enumerate(self.items):
                values = [
                    str(row + 1),
                    "",
                    "",
                    item.filename,
                    item.extension,
                    item.page_range,
                    item.status.value,
                    item.validation_summary,
                    str(item.source_path),
                ]
                for column, value in enumerate(values):
                    cell = QTableWidgetItem(value)
                    if column == COL_PDF_VALIDATION_ENABLED:
                        cell.setFlags(
                            (cell.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                            & ~Qt.ItemFlag.ItemIsEditable
                        )
                        cell.setCheckState(
                            Qt.CheckState.Checked
                            if item.pdf_validation_enabled
                            else Qt.CheckState.Unchecked
                        )
                        cell.setTextAlignment(
                            Qt.AlignmentFlag.AlignCenter
                        )
                        cell.setToolTip(
                            "체크하면 선택한 PDF 오류 항목을 이 파일에서 검사합니다."
                        )
                    elif column == COL_EXCEL_VALIDATION_ENABLED:
                        excel_source = is_excel_source(item.source_path)
                        flags = (
                            (cell.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                            & ~Qt.ItemFlag.ItemIsEditable
                        )
                        if not excel_source:
                            flags &= ~Qt.ItemFlag.ItemIsEnabled
                        cell.setFlags(flags)
                        cell.setCheckState(
                            Qt.CheckState.Checked
                            if excel_source and item.excel_validation_enabled
                            else Qt.CheckState.Unchecked
                        )
                        cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        cell.setToolTip(
                            "체크하면 원본 Excel의 주요 오류를 검사합니다."
                            if excel_source
                            else "Excel 파일에서만 사용할 수 있습니다."
                        )
                    elif column not in EDITABLE_COLUMNS:
                        cell.setFlags(
                            cell.flags() & ~Qt.ItemFlag.ItemIsEditable
                        )
                    else:
                        cell.setToolTip(
                            "더블클릭하거나 선택 후 바로 입력하여 수정할 수 있습니다."
                        )
                    if column == COL_VALIDATION:
                        cell.setToolTip(value)
                    self.table.setItem(row, column, cell)
        finally:
            self.table.blockSignals(False)
        self.statusBar().showMessage(f"파일 {len(self.items)}개")

    def _sync_page_ranges(self) -> None:
        for row, item in enumerate(self.items):
            cell = self.table.item(row, COL_PAGE_RANGE)
            if cell:
                item.page_range = cell.text().strip() or "전체"

    def _on_table_item_changed(self, cell: QTableWidgetItem) -> None:
        row = cell.row()
        column = cell.column()
        if not (0 <= row < len(self.items)):
            return

        item = self.items[row]
        if column == COL_PDF_VALIDATION_ENABLED:
            item.pdf_validation_enabled = (
                cell.checkState() == Qt.CheckState.Checked
            )
            return
        if column == COL_EXCEL_VALIDATION_ENABLED:
            item.excel_validation_enabled = (
                is_excel_source(item.source_path)
                and cell.checkState() == Qt.CheckState.Checked
            )
            return
        if column not in EDITABLE_COLUMNS:
            return

        previous_is_excel = is_excel_source(item.source_path)
        value = cell.text().strip()
        if column == COL_PAGE_RANGE:
            item.page_range = value or "전체"
            return

        try:
            if column == COL_FILENAME:
                if not value:
                    raise ValueError("파일명은 비워둘 수 없습니다.")
                item.source_path = item.source_path.with_name(value)
            elif column == COL_SOURCE_PATH:
                if not value:
                    raise ValueError("원본 경로는 비워둘 수 없습니다.")
                item.source_path = Path(value.strip('"'))
        except (OSError, ValueError) as error:
            self.statusBar().showMessage(f"입력값 오류: {error}")
        else:
            current_is_excel = is_excel_source(item.source_path)
            if not current_is_excel:
                item.excel_validation_enabled = False
            elif not previous_is_excel:
                item.excel_validation_enabled = True
        self._refresh_table()
        self.table.selectRow(row)

    def _show_table_context_menu(self, position: QPoint) -> None:
        index = self.table.indexAt(position)
        if not index.isValid():
            return
        self.table.setCurrentCell(index.row(), index.column())

        menu = QMenu(self)
        menu.addAction("선택 셀 복사", self.copy_current_cell)
        menu.addAction("파일명 복사", self.copy_current_filename)
        menu.addAction("원본 경로 복사", self.copy_current_source_path)
        menu.addAction("행 전체 복사", self.copy_current_row)
        menu.addSeparator()
        edit_action = menu.addAction("선택 셀 수정", self.edit_current_cell)
        edit_action.setEnabled(index.column() in EDITABLE_COLUMNS)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def copy_current_cell(self) -> None:
        cell = self.table.currentItem()
        if cell is not None:
            QApplication.clipboard().setText(cell.text())

    def copy_current_filename(self) -> None:
        self._copy_current_column(COL_FILENAME)

    def copy_current_source_path(self) -> None:
        self._copy_current_column(COL_SOURCE_PATH)

    def copy_current_row(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        values = [
            self.table.item(row, column).text()
            for column in range(self.table.columnCount())
            if self.table.item(row, column) is not None
        ]
        QApplication.clipboard().setText("\t".join(values))

    def _copy_current_column(self, column: int) -> None:
        row = self.table.currentRow()
        cell = self.table.item(row, column) if row >= 0 else None
        if cell is not None:
            QApplication.clipboard().setText(cell.text())

    def edit_current_cell(self) -> None:
        cell = self.table.currentItem()
        if cell is not None and cell.column() in EDITABLE_COLUMNS:
            self.table.editItem(cell)

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

        use_pdf_printer = bool(self.output_method_combo.currentData())
        printer_name = self.printer_combo.currentText().strip()
        if use_pdf_printer and not printer_name:
            QMessageBox.warning(
                self,
                "프린터 확인",
                "프린터 인식 버튼을 누르고 PDF 가상 프린터를 선택해주세요.",
            )
            return
        if use_pdf_printer:
            answer = QMessageBox.question(
                self,
                "PDF 프린터 확인",
                f"선택한 프린터: {printer_name}\n\n"
                "PDF 가상 프린터가 맞는지 확인해주세요. "
                "종이 프린터를 선택하면 실제 인쇄될 수 있습니다.\n\n"
                "이 프린터로 계속하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
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
            item.validation_checked = False
            item.validation_issues.clear()
            item.excel_validation_issues.clear()
            item.validation_unsearchable_pages.clear()
            item.validation_error = ""
        self._refresh_table()

        validation_terms = build_validation_terms(
            self.validate_ng_checkbox.isChecked(),
            self.validate_hashes_checkbox.isChecked(),
            self.validate_questions_checkbox.isChecked(),
            self.custom_validation_edit.text(),
        )

        self.conversion_thread = QThread(self)
        self.conversion_worker = ConversionWorker(
            list(self.items),
            output_directory,
            self.quality_combo.currentText(),
            self.color_combo.currentText(),
            printer_name if use_pdf_printer else "",
            validation_terms,
            self._selected_excel_validation_mode(),
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
        self.output_browse_button.setEnabled(enabled)
        self.quality_combo.setEnabled(enabled)
        self.color_combo.setEnabled(enabled)
        self.output_method_combo.setEnabled(enabled)
        self.detect_printers_button.setEnabled(enabled)
        self.printer_properties_button.setEnabled(enabled)
        self.validate_ng_checkbox.setEnabled(enabled)
        self.validate_hashes_checkbox.setEnabled(enabled)
        self.validate_questions_checkbox.setEnabled(enabled)
        self.validate_excel_fast_checkbox.setEnabled(enabled)
        self.validate_excel_precise_checkbox.setEnabled(enabled)
        self.custom_validation_edit.setEnabled(enabled)
        if enabled:
            self._update_printer_controls()
        else:
            self.printer_combo.setEnabled(False)
            self.printer_properties_button.setEnabled(False)

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
                use_pdf_printer=bool(self.output_method_combo.currentData()),
                printer_name=self.printer_combo.currentText().strip(),
                validate_ng=self.validate_ng_checkbox.isChecked(),
                validate_hashes=self.validate_hashes_checkbox.isChecked(),
                validate_questions=self.validate_questions_checkbox.isChecked(),
                validate_excel_errors=(
                    bool(self._selected_excel_validation_mode())
                ),
                excel_validation_mode=(
                    self._selected_excel_validation_mode()
                ),
                custom_validation_terms=self.custom_validation_edit.text(),
            )
        )
        event.accept()

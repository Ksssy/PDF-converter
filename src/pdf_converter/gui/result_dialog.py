from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from pdf_converter.core.models import ConversionItem


class ResultDialog(QDialog):
    def __init__(
        self,
        items: list[ConversionItem],
        success_count: int,
        failure_count: int,
        skipped_count: int,
        output_directory: Path,
        log_path: Path,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.output_directory = output_directory
        self.log_path = log_path

        self.setWindowTitle("변환 결과")
        self.resize(1050, 560)

        layout = QVBoxLayout(self)
        self.summary_label = QLabel(
            f"전체 {len(items)}개  |  "
            f"성공 {success_count}개  |  "
            f"실패 {failure_count}개  |  "
            f"건너뜀 {skipped_count}개"
        )
        layout.addWidget(self.summary_label)

        self.table = QTableWidget(len(items), 5)
        self.table.setHorizontalHeaderLabels(
            ["상태", "원본 파일", "페이지 범위", "저장 파일", "오류 내용"]
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )
        self.table.horizontalHeader().setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.Stretch,
        )

        for row, item in enumerate(items):
            values = (
                item.status.value,
                str(item.source_path),
                item.page_range,
                str(item.output_path) if item.output_path else "-",
                item.error or "-",
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip(value)
                self.table.setItem(row, column, cell)
        layout.addWidget(self.table)

        path_label = QLabel(f"저장 폴더: {output_directory}\n로그 파일: {log_path}")
        path_label.setTextInteractionFlags(path_label.textInteractionFlags())
        layout.addWidget(path_label)

        actions = QHBoxLayout()
        self.output_button = QPushButton("저장 폴더 열기")
        self.output_button.setEnabled(output_directory.is_dir())
        self.output_button.clicked.connect(self.open_output_directory)
        actions.addWidget(self.output_button)

        self.log_button = QPushButton("로그 열기")
        self.log_button.setEnabled(log_path.is_file())
        self.log_button.clicked.connect(self.open_log)
        actions.addWidget(self.log_button)

        actions.addStretch()
        close_button = QPushButton("닫기")
        close_button.clicked.connect(self.accept)
        close_button.setDefault(True)
        actions.addWidget(close_button)
        layout.addLayout(actions)

    def open_output_directory(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_directory)))

    def open_log(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.log_path)))

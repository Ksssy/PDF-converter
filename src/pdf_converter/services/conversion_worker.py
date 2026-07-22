from __future__ import annotations

from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QThread, Signal, Slot

from pdf_converter.converters import create_default_registry
from pdf_converter.converters.base import ConversionOptions
from pdf_converter.core.models import ConversionItem
from pdf_converter.services.excel_validation import (
    EXCEL_VALIDATION_PRECISE,
    inspect_excel_for_errors,
    is_excel_source,
)
from pdf_converter.services.logging_service import LoggingService
from pdf_converter.services.pdf_validation import inspect_pdf_for_errors
from pdf_converter.services.printer_service import print_pdf_with_printer


class ConversionWorker(QObject):
    item_started = Signal(int)
    item_succeeded = Signal(int, str)
    item_failed = Signal(int, str)
    item_skipped = Signal(int)
    progress_changed = Signal(int)
    completed = Signal(int, int, int, str)

    def __init__(
        self,
        items: list[ConversionItem],
        output_directory: Path,
        quality: str,
        color_mode: str,
        printer_name: str = "",
        validation_terms: list[str] | None = None,
        excel_validation_mode: str = "",
    ) -> None:
        super().__init__()
        self.items = items
        self.output_directory = output_directory
        self.quality = quality
        self.color_mode = color_mode
        self.printer_name = printer_name
        self.validation_terms = validation_terms or []
        self.excel_validation_mode = excel_validation_mode
        self._pause_event = Event()
        self._stop_event = Event()

    def set_paused(self, paused: bool) -> None:
        if paused:
            self._pause_event.set()
        else:
            self._pause_event.clear()

    def request_stop(self) -> None:
        self._stop_event.set()
        self._pause_event.clear()

    @Slot()
    def run(self) -> None:
        registry = create_default_registry()
        logger = LoggingService()
        success_count = 0
        failure_count = 0
        skipped_count = 0
        log_path = logger.write(f"변환 시작: 총 {len(self.items)}개")

        for index, item in enumerate(self.items):
            while self._pause_event.is_set() and not self._stop_event.is_set():
                QThread.msleep(100)

            if self._stop_event.is_set():
                for remaining_index in range(index, len(self.items)):
                    self.item_skipped.emit(remaining_index)
                    skipped_count += 1
                break

            self.item_started.emit(index)
            try:
                if (
                    item.excel_validation_enabled
                    and self.excel_validation_mode
                    and is_excel_source(item.source_path)
                ):
                    item.validation_checked = True
                    try:
                        item.excel_validation_issues = (
                            inspect_excel_for_errors(
                                item.source_path,
                                recalculate=(
                                    self.excel_validation_mode
                                    == EXCEL_VALIDATION_PRECISE
                                ),
                            )
                        )
                    except Exception as validation_error:
                        _append_validation_error(item, str(validation_error))
                        logger.write(
                            f"Excel 원본 오류 검사 실패 | "
                            f"{item.source_path} | {validation_error}"
                        )
                    else:
                        logger.write(
                            f"Excel 원본 오류 검사 | {item.source_path} | "
                            f"{item.validation_summary}"
                        )

                converter = registry.resolve(item.source_path)
                output_path = converter.convert(
                    item.source_path,
                    ConversionOptions(
                        output_directory=self.output_directory,
                        page_range=item.page_range,
                        quality=self.quality,
                        color_mode=self.color_mode,
                    ),
                )
                if item.pdf_validation_enabled and self.validation_terms:
                    item.validation_checked = True
                    try:
                        report = inspect_pdf_for_errors(
                            output_path,
                            self.validation_terms,
                        )
                    except Exception as validation_error:
                        _append_validation_error(item, str(validation_error))
                        logger.write(
                            f"PDF 오류 검사 실패 | {item.source_path} | "
                            f"{validation_error}"
                        )
                    else:
                        item.validation_issues = report.issues
                        item.validation_unsearchable_pages = (
                            report.unsearchable_pages
                        )
                        logger.write(
                            f"PDF 오류 검사 | {item.source_path} | "
                            f"{item.validation_summary}"
                        )
                if self.printer_name:
                    output_path = print_pdf_with_printer(
                        output_path,
                        self.printer_name,
                        self.quality,
                    )
            except Exception as error:
                failure_count += 1
                message = str(error)
                logger.write(f"실패 | {item.source_path} | {message}")
                self.item_failed.emit(index, message)
            else:
                success_count += 1
                logger.write(f"성공 | {item.source_path} -> {output_path}")
                self.item_succeeded.emit(index, str(output_path))

            completed_count = success_count + failure_count + skipped_count
            self.progress_changed.emit(
                round(completed_count / len(self.items) * 100) if self.items else 100
            )

        logger.write(
            f"변환 종료: 성공 {success_count}, 실패 {failure_count}, 건너뜀 {skipped_count}"
        )
        self.progress_changed.emit(100)
        self.completed.emit(
            success_count,
            failure_count,
            skipped_count,
            str(log_path),
        )


def _append_validation_error(item: ConversionItem, message: str) -> None:
    if item.validation_error:
        item.validation_error = f"{item.validation_error} | {message}"
    else:
        item.validation_error = message

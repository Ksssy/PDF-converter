from __future__ import annotations

from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QThread, Signal, Slot

from pdf_converter.converters import create_default_registry
from pdf_converter.converters.base import ConversionOptions
from pdf_converter.core.models import ConversionItem
from pdf_converter.services.logging_service import LoggingService


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
    ) -> None:
        super().__init__()
        self.items = items
        self.output_directory = output_directory
        self.quality = quality
        self.color_mode = color_mode
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

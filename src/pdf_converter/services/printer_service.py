from __future__ import annotations

import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pymupdf
from PySide6.QtCore import QRectF, QSizeF
from PySide6.QtGui import QImage, QPageSize, QPainter
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo


PRINT_DPI = {
    "최소용량": 200,
    "일반": 300,
    "고품질": 450,
}


def list_installed_printers() -> list[str]:
    return sorted(set(QPrinterInfo.availablePrinterNames()), key=str.casefold)


def printer_exists(printer_name: str) -> bool:
    return bool(printer_name) and not QPrinterInfo.printerInfo(printer_name).isNull()


def open_printer_properties(printer_name: str) -> None:
    """Open the selected Windows driver's printing-preferences dialog."""
    if os.name != "nt":
        raise RuntimeError("프린터 속성은 Windows에서만 열 수 있습니다.")
    if not printer_exists(printer_name):
        raise RuntimeError(
            f"선택한 프린터가 현재 Windows에 없습니다: {printer_name}. "
            "프린터 인식 버튼을 다시 눌러주세요."
        )

    result = subprocess.run(
        [
            "rundll32.exe",
            "printui.dll,PrintUIEntry",
            "/e",
            "/n",
            printer_name,
        ],
        check=False,
        close_fds=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise RuntimeError(
            f"프린터 속성을 열지 못했습니다: {printer_name} "
            f"(오류 코드 {result.returncode})"
        )


def _fit_rect(container: QRectF, width: int, height: int) -> QRectF:
    scale = min(container.width() / width, container.height() / height)
    draw_width = width * scale
    draw_height = height * scale
    return QRectF(
        container.x() + (container.width() - draw_width) / 2,
        container.y() + (container.height() - draw_height) / 2,
        draw_width,
        draw_height,
    )


def print_pdf_with_printer(
    source_pdf: Path,
    printer_name: str,
    quality: str,
) -> Path:
    """Recreate source_pdf through a selected Windows PDF virtual printer."""
    temporary_output = source_pdf.with_name(
        f".{source_pdf.stem}.{uuid4().hex}.printer.pdf"
    )
    dpi = PRINT_DPI.get(quality, PRINT_DPI["일반"])

    printer_info = QPrinterInfo.printerInfo(printer_name)
    if printer_info.isNull():
        raise RuntimeError(
            f"선택한 프린터가 현재 Windows에 없습니다: {printer_name}. "
            "프린터 인식 버튼을 다시 눌러주세요."
        )

    printer = QPrinter(printer_info, QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.NativeFormat)
    printer.setOutputFileName(str(temporary_output))
    printer.setResolution(dpi)

    try:
        with pymupdf.open(source_pdf) as document:
            if document.page_count == 0:
                raise RuntimeError("출력할 PDF 페이지가 없습니다.")

            first_page_size = document[0].rect
            printer.setPageSize(
                QPageSize(
                    QSizeF(first_page_size.width, first_page_size.height),
                    QPageSize.Unit.Point,
                )
            )

            painter = QPainter()
            if not painter.begin(printer):
                raise RuntimeError(
                    f"선택한 프린터를 시작할 수 없습니다: {printer_name}"
                )
            try:
                for page_number in range(document.page_count):
                    if page_number and not printer.newPage():
                        raise RuntimeError("프린터에서 새 페이지를 만들지 못했습니다.")
                    pixmap = document[page_number].get_pixmap(
                        dpi=dpi,
                        colorspace=pymupdf.csRGB,
                        alpha=False,
                        annots=True,
                    )
                    image = QImage(
                        pixmap.samples,
                        pixmap.width,
                        pixmap.height,
                        pixmap.stride,
                        QImage.Format.Format_RGB888,
                    ).copy()
                    page_rect = QRectF(
                        printer.pageRect(QPrinter.Unit.DevicePixel)
                    )
                    painter.drawImage(
                        _fit_rect(page_rect, image.width(), image.height()),
                        image,
                    )
            finally:
                painter.end()

        if not temporary_output.is_file():
            raise RuntimeError(
                "선택한 프린터가 출력 파일을 만들지 않았습니다. "
                "PDF 가상 프린터인지 확인해주세요."
            )
        if temporary_output.read_bytes()[:4] != b"%PDF":
            raise RuntimeError(
                "선택한 프린터의 출력이 PDF 형식이 아닙니다. "
                "PDF 가상 프린터를 선택해주세요."
            )

        temporary_output.replace(source_pdf)
        return source_pdf
    finally:
        temporary_output.unlink(missing_ok=True)

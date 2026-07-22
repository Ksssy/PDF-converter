from __future__ import annotations

from contextlib import suppress
from pathlib import Path
import winreg

import pythoncom
from win32com.client import DispatchEx

from pdf_converter.converters.base import BaseConverter, ConversionOptions


HWP_AUTOMATION_MODULES_KEY = r"Software\HNC\HwpAutomation\Modules"


def find_registered_security_module() -> str | None:
    """Return the first valid HWP automation security-module registry name."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, HWP_AUTOMATION_MODULES_KEY)
    except OSError:
        return None

    with key:
        index = 0
        while True:
            try:
                module_name, module_path, _ = winreg.EnumValue(key, index)
            except OSError:
                break
            if module_name and isinstance(module_path, str) and Path(module_path).is_file():
                return module_name
            index += 1
    return None


class HwpConverter(BaseConverter):
    supported_extensions = frozenset({".hwp", ".hwpx"})

    def convert(self, source: Path, options: ConversionOptions) -> Path:
        if options.color_mode == "흑백":
            raise RuntimeError("한글 흑백 PDF 변환은 아직 지원하지 않습니다.")

        def export(target: Path) -> None:
            pythoncom.CoInitialize()
            application = None
            try:
                application = DispatchEx("HWPFrame.HwpObject")
                security_module = find_registered_security_module()
                module_registered = False
                if security_module:
                    try:
                        module_registered = bool(
                            application.RegisterModule(
                                "FilePathCheckDLL",
                                security_module,
                            )
                        )
                    except Exception:
                        with suppress(Exception):
                            application.Quit()
                        application = DispatchEx("HWPFrame.HwpObject")

                # 보안 모듈이 없거나 호환되지 않으면 접근 승인 창을 사용자가 볼 수 있어야 한다.
                application.XHwpWindows.Item(0).Visible = not module_registered
                opened = application.Open(str(source.resolve()), "", "")
                if not opened:
                    raise RuntimeError(
                        "한글 파일을 열지 못했습니다. 한글의 파일 접근 승인 창을 확인해주세요."
                    )

                saved = application.SaveAs(str(target.resolve()), "PDF", "")
                if not saved:
                    raise RuntimeError("한글이 PDF 저장을 완료하지 못했습니다.")
            except Exception as error:
                if isinstance(error, RuntimeError):
                    raise
                raise RuntimeError(f"한글 PDF 변환 실패: {error}") from error
            finally:
                if application is not None:
                    with suppress(Exception):
                        application.Quit()
                pythoncom.CoUninitialize()

        return self._export_and_finalize(source, options, export)

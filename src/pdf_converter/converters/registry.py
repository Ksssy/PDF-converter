from __future__ import annotations

from pathlib import Path

from pdf_converter.converters.base import BaseConverter


class ConverterRegistry:
    def __init__(self) -> None:
        self._converters: list[BaseConverter] = []

    def register(self, converter: BaseConverter) -> None:
        self._converters.append(converter)

    def resolve(self, source: Path) -> BaseConverter:
        for converter in self._converters:
            if converter.supports(source):
                return converter
        raise ValueError(f"지원하지 않는 파일 형식입니다: {source.suffix}")

from pdf_converter.converters.excel import ExcelConverter
from pdf_converter.converters.hwp import HwpConverter
from pdf_converter.converters.powerpoint import PowerPointConverter
from pdf_converter.converters.registry import ConverterRegistry
from pdf_converter.converters.word import WordConverter


def create_default_registry() -> ConverterRegistry:
    registry = ConverterRegistry()
    registry.register(HwpConverter())
    registry.register(WordConverter())
    registry.register(ExcelConverter())
    registry.register(PowerPointConverter())
    return registry


__all__ = [
    "ExcelConverter",
    "HwpConverter",
    "PowerPointConverter",
    "WordConverter",
    "create_default_registry",
]

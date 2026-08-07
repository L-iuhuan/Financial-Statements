"""Excel 文件读取器: 使用 openpyxl 读取 Excel 文件，返回 RawSheetData。

将 openpyxl Workbook 转换为与导入框架无关的 RawSheetData 结构，
使 item_extractor 和 report_identifier 不直接依赖 openpyxl。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import openpyxl
from loguru import logger
from openpyxl.worksheet.worksheet import Worksheet


@dataclass
class RawSheetData:
    """一个工作表的原始数据。

    Attributes:
        name: 工作表名称
        headers: 列标题列表（第一行）
        rows: 数据行列表，每行是 dict，键为列标题，额外包含 "_row" 键（行号）
    """

    name: str
    headers: list[str] = field(default_factory=list)
    rows: list[dict[str, object]] = field(default_factory=list)


def read_excel(file_path: str) -> dict[str, RawSheetData]:
    """读取 Excel 文件，返回所有工作表的原始数据。

    Args:
        file_path: Excel 文件路径

    Returns:
        字典，键为工作表名称，值为 RawSheetData

    Raises:
        FileNotFoundError: 文件不存在
    """
    path = file_path
    if not isinstance(path, str):
        path = str(path)

    logger.info(f"正在读取 Excel 文件: {path}")

    try:
        wb = openpyxl.load_workbook(path, data_only=True)
    except FileNotFoundError:
        raise
    except OSError as e:
        raise FileNotFoundError(f"无法打开文件「{path}」: {e}") from e

    result: dict[str, RawSheetData] = {}

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        raw = _read_sheet(sheet)
        result[sheet_name] = raw
        logger.debug(f"  工作表「{sheet_name}」: {len(raw.rows)} 行数据")

    wb.close()
    logger.info(f"读取完成，共 {len(result)} 个工作表")
    return result


def _read_sheet(sheet: Worksheet) -> RawSheetData:
    """读取单个工作表的数据。

    Args:
        sheet: openpyxl 工作表对象

    Returns:
        RawSheetData 对象
    """
    header_row = _find_header_row(sheet)
    headers = _read_headers(sheet, header_row)
    rows = _read_rows(sheet, headers, header_row)
    return RawSheetData(name=sheet.title, headers=headers, rows=rows)


def _find_header_row(sheet: Worksheet) -> int:
    """查找表头行（包含"项目"列的行）。

    扫描前 5 行，找到第一列包含"项目"的行作为表头行。
    若未找到，默认返回第 1 行。

    Args:
        sheet: 工作表对象

    Returns:
        表头行号（从 1 开始）
    """
    for row_idx in range(1, min(6, sheet.max_row + 1)):
        first_cell = sheet.cell(row=row_idx, column=1).value
        if first_cell is not None and str(first_cell).strip() == "项目":
            return row_idx
    return 1


def _read_headers(sheet: Worksheet, header_row: int) -> list[str]:
    """读取指定行作为列标题。

    Args:
        sheet: 工作表对象
        header_row: 表头行号

    Returns:
        列标题列表
    """
    headers: list[str] = []
    for col_idx in range(1, sheet.max_column + 1):
        value = sheet.cell(row=header_row, column=col_idx).value
        headers.append(str(value) if value is not None else f"列{col_idx}")
    return headers


def _read_rows(sheet: Worksheet, headers: list[str], header_row: int) -> list[dict[str, object]]:
    """读取数据行（从表头行的下一行开始）。

    Args:
        sheet: 工作表对象
        headers: 列标题列表
        header_row: 表头行号

    Returns:
        数据行列表
    """
    rows: list[dict[str, object]] = []

    for row_idx in range(header_row + 1, sheet.max_row + 1):
        row_data: dict[str, object] = {"_row": row_idx}
        is_empty = True

        for col_idx, header in enumerate(headers, 1):
            value = sheet.cell(row=row_idx, column=col_idx).value
            if value is not None:
                is_empty = False
            row_data[header] = value

        if not is_empty:
            rows.append(row_data)

    return rows

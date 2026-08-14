"""PDF 文件读取器: 使用 pdfplumber 读取 PDF 财务报表，返回 RawSheetData。

将 PDF 中的表格提取为与 Excel 导入框架兼容的 RawSheetData 结构，
使 item_extractor 和 report_identifier 无需修改即可处理 PDF 数据。

检测策略:
- 每页提取表格，识别标题行（包含"资产负债表"/"利润表"/"现金流量表"）
- 标题下方第一行为列标题（项目 + 金额列）
- 后续行为数据行

行号语义 (与 Excel 路径对齐, 见 D-01):
- 数据行 "_row" = 页码 * _PDF_ROW_BASE + 表内行号（1-based），
  保证「第X页表内第N行」可定位到 PDF 原始文件。
"""

from __future__ import annotations

from pathlib import Path

import pdfplumber
from loguru import logger

from fsa.core.importer.amount_parser import parse_amount
from fsa.core.importer.excel_reader import RawSheetData

# 报表标题关键词 -> 报表类型（用于边界检测）
_TITLE_KEYWORDS: list[str] = [
    "合并资产负债表",
    "资产负债表",
    "合并利润表",
    "利润表",
    "合并现金流量表",
    "现金流量表",
]

# 金额列标题匹配（pdfplumber 提取的文本可能略有差异）
_AMOUNT_HEADER_CANDIDATES: list[str] = [
    "期末余额", "期末数", "期末",
    "年初余额", "年初数", "期初余额", "期初数",
    "本期金额", "本期数", "本期",
    "上期金额", "上期数", "上期",
]

# PDF 行号编码基数: 行号 = 页码 * _PDF_ROW_BASE + 表内行号（1-based）。
# Excel 工作表最大行号为 1,048,576，恒小于该基数，
# 因此 audit_exporter 可按 `row >= _PDF_ROW_BASE` 判定来源并解码为「第X页表内第N行」。
_PDF_ROW_BASE = 10_000_000


def read_pdf(file_path: str) -> dict[str, RawSheetData]:
    """读取 PDF 文件，提取财务报表为 RawSheetData。

    每页检测一个报表标题，标题行作为 sheet name，
    标题下方表格的列标题行作为 headers，数据行为 rows。

    Args:
        file_path: PDF 文件路径

    Returns:
        字典，键为报表标题（如"资产负债表"），值为 RawSheetData

    Raises:
        FileNotFoundError: 文件不存在
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    logger.info(f"正在读取 PDF 文件: {file_path}")

    result: dict[str, RawSheetData] = {}

    with pdfplumber.open(str(path)) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            if not tables:
                logger.debug(f"  第 {page_num} 页: 未检测到表格，跳过")
                continue

            raw = _extract_sheet_from_page(tables[0], page_num)
            if raw is None:
                logger.debug(f"  第 {page_num} 页: 表格未识别为财务报表，跳过")
                continue

            result[raw.name] = raw
            logger.info(f"  第 {page_num} 页: 识别报表「{raw.name}」，{len(raw.rows)} 行数据")

    logger.info(f"PDF 读取完成，共识别 {len(result)} 张报表")
    return result


def _extract_sheet_from_page(
    table: list[list[str | None]],
    page_num: int,
) -> RawSheetData | None:
    """从单页表格提取一个 RawSheetData。

    检测第1行是否为报表标题，若是则取第2行为表头，后续行为数据行。

    Args:
        table: pdfplumber 提取的表格数据
        page_num: 页码（用于日志）

    Returns:
        RawSheetData 或 None（若表格非财务报表）
    """
    if len(table) < 2:
        return None

    # 检测标题行（第1行第1列）
    title_cell = _safe_str(table[0][0])
    if not title_cell:
        return None

    title = _detect_title(title_cell)
    if title is None:
        return None

    # 查找表头行（跳过标题行后第一个非空行）
    header_row_idx = _find_header_row(table, start=1)
    if header_row_idx is None:
        return None

    headers = _normalize_headers(table[header_row_idx])
    if not headers or "项目" not in headers:
        # 尝试在标题行与数据之间查找表头
        logger.debug(f"  第 {page_num} 页: 表头行未找到'项目'列，headers={headers}")
        return None

    # 解析数据行
    rows = _parse_data_rows(table, headers, header_row_idx + 1, page_num)
    if not rows:
        logger.debug(f"  第 {page_num} 页: 无有效数据行")
        return None

    return RawSheetData(name=title, headers=headers, rows=rows)


def _detect_title(cell_text: str) -> str | None:
    """检测单元格文本是否为报表标题。

    Args:
        cell_text: 单元格文本

    Returns:
        匹配的标题文本，或 None
    """
    text = cell_text.strip()
    for keyword in _TITLE_KEYWORDS:
        if keyword in text:
            return text
    return None


def _find_header_row(
    table: list[list[str | None]],
    start: int = 1,
) -> int | None:
    """查找表头行（包含"项目"列的行）。

    Args:
        table: 表格数据
        start: 起始搜索行号（从 0 开始）

    Returns:
        表头行号，未找到返回 None
    """
    for i in range(start, min(start + 5, len(table))):
        for cell in table[i]:
            if _safe_str(cell) == "项目":
                return i
    return None


def _normalize_headers(row: list[str | None]) -> list[str]:
    """标准化表头行，去除 None 和空白。

    Args:
        row: 表头行原始数据

    Returns:
        标准化后的表头列表
    """
    headers: list[str] = []
    for cell in row:
        text = _safe_str(cell)
        if text:
            headers.append(text)
        else:
            headers.append("")
    return headers


def _parse_data_rows(
    table: list[list[str | None]],
    headers: list[str],
    start_row: int,
    page_num: int,
) -> list[dict[str, object]]:
    """解析数据行。

    每行的 "_row" 编码为 `page_num * _PDF_ROW_BASE + 表内行号`，
    表内行号为该页提取表格中的 1-based 行（含标题行/表头行），
    保证用户可按「第X页表内第N行」定位到 PDF 原始文件 (P3 可审计可溯源)。

    Args:
        table: 表格数据
        headers: 列标题列表
        start_row: 数据起始行号（0-based 表格下标）
        page_num: 页码（从 1 开始）

    Returns:
        数据行列表，每行为 dict
    """
    rows: list[dict[str, object]] = []

    for i in range(start_row, len(table)):
        table_row = table[i]
        if _is_empty_row(table_row):
            continue

        row_data: dict[str, object] = {"_row": page_num * _PDF_ROW_BASE + i + 1}
        is_empty = True

        for col_idx, header in enumerate(headers):
            if col_idx >= len(table_row):
                break
            value = _parse_cell_value(table_row[col_idx])
            if value is not None:
                is_empty = False
            row_data[header] = value

        if not is_empty:
            rows.append(row_data)

    return rows


def _is_empty_row(row: list[str | None]) -> bool:
    """判断行是否为空（所有单元格均为 None 或空字符串）。"""
    return all(_safe_str(cell) == "" for cell in row)


def _safe_str(value: str | None) -> str:
    """安全地将值转为字符串，None 返回空字符串。"""
    if value is None:
        return ""
    return str(value).strip()


def _parse_cell_value(value: str | None) -> object:
    """解析单元格值：尝试转为数字，失败则返回原字符串。

    支持千分位逗号/空格、括号负数、占位符（"-"、"—"→0.0）、科学计数法。
    空单元格（None/纯空白）返回 None，占位符不被当作真空值丢弃。

    Args:
        value: 单元格原始值

    Returns:
        解析后的值（float、str 或 None）
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    parsed = parse_amount(value)
    if parsed is None:
        return text
    return parsed

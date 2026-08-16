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

import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
from loguru import logger
from pdfminer.pdfexceptions import PDFException
from pdfplumber.utils.exceptions import MalformedPDFException, PdfminerException

from fsa.core.exceptions import FSAError
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
    "期末余额",
    "期末数",
    "期末",
    "年初余额",
    "年初数",
    "期初余额",
    "期初数",
    "本期金额",
    "本期数",
    "本期",
    "上期金额",
    "上期数",
    "上期",
]

# PDF 行号编码基数: 行号 = 页码 * _PDF_ROW_BASE + 表内行号（1-based）。
# Excel 工作表最大行号为 1,048,576，恒小于该基数，
# 因此 audit_exporter 可按 `row >= _PDF_ROW_BASE` 判定来源并解码为「第X页表内第N行」。
_PDF_ROW_BASE = 10_000_000


@dataclass
class PdfReadDiagnostics:
    """PDF 解析诊断信息 (页数/表数/跳过情况/置信度)。

    与 RawSheetData 分离, 供导入层生成"建议优先使用 Excel"提示与审计留痕。
    """

    page_count: int = 0
    table_count: int = 0
    recognized_sheets: list[str] = field(default_factory=list)
    continuation_count: int = 0
    skipped_tables: int = 0
    skipped_rows: int = 0
    pages_without_tables: int = 0

    @property
    def confidence(self) -> str:
        """解析置信度: 无跳过为高; 少量跳过为中; 大量跳过/无表格为低。"""
        if self.table_count == 0:
            return "低"
        total_skipped = self.skipped_tables + self.skipped_rows
        if total_skipped == 0 and self.pages_without_tables == 0:
            return "高"
        if total_skipped <= max(2, self.table_count):
            return "中"
        return "低"

    def summary_text(self) -> str:
        """生成面向用户的中文诊断摘要。"""
        parts = [f"PDF 共 {self.page_count} 页、检测到 {self.table_count} 个表格"]
        if self.recognized_sheets:
            parts.append("识别报表: " + "、".join(dict.fromkeys(self.recognized_sheets)))
        if self.continuation_count:
            parts.append(f"跨页续表合并 {self.continuation_count} 次")
        if self.skipped_tables:
            parts.append(f"跳过 {self.skipped_tables} 个未识别表格")
        if self.skipped_rows:
            parts.append(f"跳过 {self.skipped_rows} 行异常数据")
        if self.pages_without_tables:
            parts.append(f"{self.pages_without_tables} 页未检测到表格")
        parts.append(f"解析置信度: {self.confidence}")
        return "；".join(parts)


def read_pdf(
    file_path: str,
    diagnostics: PdfReadDiagnostics | None = None,
) -> dict[str, RawSheetData]:
    """读取 PDF 文件，提取财务报表为 RawSheetData。

    每页检测报表标题/表头，同标题跨页续表与同页多表合并为同一张报表。

    Args:
        file_path: PDF 文件路径
        diagnostics: 可选输出对象, 填充页数/表数/跳过统计与解析置信度

    Returns:
        字典，键为报表标题（如"资产负债表"），值为 RawSheetData

    Raises:
        FileNotFoundError: 文件不存在
        FSAError: PDF 文件损坏或已加密，无法读取
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    logger.info(f"正在读取 PDF 文件: {file_path}")

    result: dict[str, RawSheetData] = {}
    diag = diagnostics or PdfReadDiagnostics()

    try:
        with pdfplumber.open(str(path)) as pdf:
            diag.page_count = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages, 1):
                tables = page.extract_tables()
                if not tables:
                    diag.pages_without_tables += 1
                    logger.debug(f"  第 {page_num} 页: 未检测到表格，跳过")
                    continue

                for table in tables:
                    diag.table_count += 1
                    raw = _extract_sheet_from_page(table, page_num, diag)
                    if raw is None:
                        # 跨页续表: 次页可能没有报表标题, 用表头匹配已有报表
                        raw = _extract_continuation_sheet(table, page_num, result, diag)
                    if raw is None:
                        diag.skipped_tables += 1
                        continue

                    # C6: 同标题跨页续表/同页多表 — 合并数据行而非覆盖
                    if raw.name in result:
                        existing = result[raw.name]
                        existing.rows.extend(raw.rows)
                        diag.continuation_count += 1
                        logger.info(
                            f"  第 {page_num} 页: 合并到报表「{raw.name}」，"
                            f"新增 {len(raw.rows)} 行，现有 {len(existing.rows)} 行"
                        )
                    else:
                        result[raw.name] = raw
                        diag.recognized_sheets.append(raw.name)
                        logger.info(f"  第 {page_num} 页: 识别报表「{raw.name}」，{len(raw.rows)} 行数据")
    except (PDFException, PdfminerException, MalformedPDFException) as error:
        # pdfminer/pdfplumber 异常族 (语法错误/加密/结构损坏等) 统一转中文错误 (P4)
        raise FSAError("PDF 文件损坏或已加密，无法读取，请改用 Excel 报表") from error

    logger.info(f"PDF 读取完成，共识别 {len(result)} 张报表")
    return result


def _extract_sheet_from_page(
    table: list[list[str | None]],
    page_num: int,
    diag: PdfReadDiagnostics | None = None,
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
    rows = _parse_data_rows(table, headers, header_row_idx + 1, page_num, diag)
    if not rows:
        logger.debug(f"  第 {page_num} 页: 无有效数据行")
        return None

    return RawSheetData(name=title, headers=headers, rows=rows)


def _extract_continuation_sheet(
    table: list[list[str | None]],
    page_num: int,
    existing: dict[str, RawSheetData],
    diag: PdfReadDiagnostics | None = None,
) -> RawSheetData | None:
    """识别无标题行的跨页续表。

    策略:
    1. 在表格前 5 行查找表头行 ("项目"列)
    2. 与已识别报表的 headers 精确匹配 (非空列集合一致)
    3. 仅当匹配唯一一张报表时, 按已有 headers 解析并返回该报表名

    无法唯一匹配时返回 None (宁可漏报, 不把数据错并到其他报表)。
    """
    header_row_idx = _find_header_row(table, start=0)
    if header_row_idx is None:
        return None
    headers = _normalize_headers(table[header_row_idx])
    if "项目" not in headers:
        return None

    header_key = _header_signature(headers)
    matches = [name for name, raw in existing.items() if _header_signature(raw.headers) == header_key]
    if len(matches) != 1:
        return None

    matched = existing[matches[0]]
    rows = _parse_data_rows(table, matched.headers, header_row_idx + 1, page_num, diag)
    if not rows:
        return None
    return RawSheetData(name=matched.name, headers=matched.headers, rows=rows)


def _header_signature(headers: list[str]) -> tuple[str, ...]:
    """表头签名: 去空白后的非空列名序列, 用于跨页续表匹配。"""
    return tuple(_normalize_cell_text(header) for header in headers if _normalize_cell_text(header))


def _normalize_cell_text(value: object) -> str:
    """去除单元格文本全部空白, 用于表头签名比较。"""
    if value is None:
        return ""
    return re.sub(r"\s+", "", str(value))


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
    diag: PdfReadDiagnostics | None = None,
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
    header_count = len(headers)

    for i in range(start_row, len(table)):
        table_row = table[i]
        if _is_empty_row(table_row):
            continue

        # 非空单元格计数: 用于行宽校验
        non_empty_count = sum(1 for cell in table_row if _safe_str(cell) != "")

        # C5: 行宽校验 — 数据行非空单元格数超过表头列数时跳过
        # 短行则自然对齐，但长行会导致值错位 (P1 宁可漏报)
        if non_empty_count > header_count:
            if diag is not None:
                diag.skipped_rows += 1
            logger.warning(
                f"  第 {page_num} 页第 {i + 1} 行: "
                f"非空单元格数({non_empty_count})超过表头列数({header_count})，跳过该行"
            )
            continue

        row_data: dict[str, object] = {"_row": page_num * _PDF_ROW_BASE + i + 1}
        is_empty = True

        for col_idx, header in enumerate(headers):
            if col_idx >= len(table_row):
                row_data[header] = None
                continue
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

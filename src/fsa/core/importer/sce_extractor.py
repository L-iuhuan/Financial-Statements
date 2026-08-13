"""所有者权益变动表 (SCE) 矩阵提取器。

SCE 是矩阵式报表, 不同于三大主表的"项目+金额"列表布局:
- 表头行: 项目 | 实收资本 | 资本公积 | 减:库存股 | 其他综合收益 | 盈余公积 | 未分配利润 | ...
- 数据行: 一、上年年末余额 / 二、本年年初余额 / (一)综合收益总额 / ... / 四、本年年末余额

本提取器将 (权益组成列, 变动类型行) 的单元格映射为 sce_* 变量。
仅 Excel 路径使用; PDF 的 SCE 矩阵提取暂不支持。
"""

from __future__ import annotations

import re

from loguru import logger

from fsa.core.importer.excel_reader import RawSheetData
from fsa.core.importer.name_mapper import clean_name
from fsa.core.models.report import ReportItem

# 权益组成列名 -> 基础 key (实收资本(或股本) 等带括号的变体也覆盖)
_COMPONENT_KEYS: dict[str, str] = {
    "实收资本": "sce_paid_in_capital",
    "股本": "sce_paid_in_capital",
    "资本公积": "sce_capital_reserve",
    "库存股": "sce_treasury_stock",
    "其他综合收益": "sce_other_comprehensive",
    "盈余公积": "sce_surplus_reserve",
    "未分配利润": "sce_undistributed_profit",
    "少数股东权益": "sce_minority_interest",
    "所有者权益合计": "sce_equity_total",
    "股东权益合计": "sce_equity_total",
}

# 期末类行标签关键词 -> 后缀
_ENDING_ROW_KEYWORDS = ("年末余额", "期末余额", "年末数", "期末数")
# 期初类行标签关键词 -> 后缀
_BEGINNING_ROW_KEYWORDS = ("年初余额", "期初余额", "年初数", "期初数", "上年年末余额")
# 综合收益总额行 -> 后缀
_COMPREHENSIVE_KEYWORD = "综合收益总额"

# 综合收益行中仅这些组成列需要提取 _comprehensive 变量
_COMPREHENSIVE_COLUMNS = frozenset({
    "sce_undistributed_profit",
    "sce_other_comprehensive",
    "sce_equity_total",
})

_PREFIX_RE = re.compile(r"^[一二三四五六七八九十]+、|^减[：:]|^加[：:]|^[（(][一二三四五六七八九十]+[)）]|^\s+")


def extract_sce_items(raw: RawSheetData) -> list[ReportItem]:
    """从 SCE 矩阵中提取权益组成项目。

    Args:
        raw: SCE 工作表原始数据 (矩阵布局)

    Returns:
        ReportItem 列表 (sce_* keys)
    """
    header_rows = raw.header_rows or [raw.headers]
    column_map = _build_column_map(raw.headers, header_rows)
    if not column_map:
        logger.warning(f"工作表「{raw.name}」未识别到权益组成列")
        return []

    items: list[ReportItem] = []
    seen: set[str] = set()
    for row in raw.rows:
        label = _clean_label(str(row.get("项目") or ""))
        suffix = _row_suffix(label)
        if suffix is None:
            continue
        items.extend(_extract_row(row, label, suffix, column_map, seen))

    logger.info(f"  从工作表「{raw.name}」提取了 {len(items)} 个 SCE 项目")
    return items


def _build_column_map(headers: list[str], header_rows: list[list[str]]) -> dict[str, str]:
    """构建 数据行键名 -> 基础 key 映射 (跳过"项目"列)。

    支持多行表头: 对每一列，从各层表头中取第一个非空标签，
    例如 "股本/资本公积/减：库存股..." 与 "优先股/永续债/其他..."
    两层合并时只取上一层的有效组件名。映射键使用行数据的实际列名
    （headers 中可能带 #2 等去重后缀）。
    """
    mapping: dict[str, str] = {}
    column_count = len(headers)
    for col_idx in range(column_count):
        label = ""
        for row in header_rows:
            if col_idx < len(row):
                label = str(row[col_idx]).strip()
            if label:
                break
        cleaned = _clean_label(label)
        if cleaned in ("项目", ""):
            continue
        key = _COMPONENT_KEYS.get(cleaned)
        if key is not None:
            mapping[headers[col_idx]] = key
    return mapping


def _clean_label(text: str) -> str:
    """清理行/列标签: 去除序号前缀、减:、括号序号、首尾空格。"""
    result = text.strip()
    result = _PREFIX_RE.sub("", result).strip()
    return clean_name(result)


def _row_suffix(label: str) -> str | None:
    """判断行标签对应的变量后缀 (_ending/_beginning/_comprehensive/None)。

    注意顺序: "上年年末余额"含"年末余额"但实为上年期末=本年期初,
    故先匹配期初关键词 (上年年末/年初/期初), 再匹配期末关键词。
    """
    if not label:
        return None
    if _COMPREHENSIVE_KEYWORD in label:
        return "_comprehensive"
    if any(k in label for k in _BEGINNING_ROW_KEYWORDS):
        return "_beginning"
    if any(k in label for k in _ENDING_ROW_KEYWORDS):
        return "_ending"
    return None


def _extract_row(
    row: dict[str, object],
    label: str,
    suffix: str,
    column_map: dict[str, str],
    seen: set[str],
) -> list[ReportItem]:
    """提取一行中所有权益组成列的金额。"""
    items: list[ReportItem] = []
    for header, base_key in column_map.items():
        # 综合收益行只提取关键组成列
        if suffix == "_comprehensive" and base_key not in _COMPREHENSIVE_COLUMNS:
            continue
        key = f"{base_key}{suffix}"
        if key in seen:
            continue
        amount = _to_float(row.get(header))
        if amount is None:
            continue
        seen.add(key)
        items.append(
            ReportItem(
                key=key,
                name=f"{_clean_label(header)}({label})",
                amount=amount,
                row=_to_row_num(row),
                column=header,
            )
        )
    return items


def _to_float(value: object) -> float | None:
    """安全转换为 float, 失败返回 None。"""
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None


def _to_row_num(row: dict[str, object]) -> int:
    """提取行号 (_row 键)。"""
    value = row.get("_row")
    if isinstance(value, (int, float)):
        return int(value)
    return 0

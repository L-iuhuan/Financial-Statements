"""报表项目提取器: 从 RawSheetData 提取 ReportItem 对象。

针对不同企业的报表格式提供通用适配能力:
- 自动识别项目列与主/次金额列（标准列名、期间列名、纯数值列回退）
- 资产负债表支持左右双栏（资产 | 负债和所有者权益）
- 项目名统一清洗（前缀/行尾括号注释/冒号）
- 现金流量表补充资料区域映射为 cf_notes_ 前缀
"""

from __future__ import annotations

import re

from loguru import logger

from fsa.core.importer.amount_parser import parse_amount
from fsa.core.importer.excel_reader import RawSheetData
from fsa.core.importer.name_mapper import clean_name, get_key, get_supplementary_key
from fsa.core.models.report import ReportItem, ReportType

_NAME_COLUMN_CANDIDATES = ["项目", "项目名称", "科目", "科目名称"]

_PRIMARY_COLUMN_CANDIDATES: dict[ReportType, list[str]] = {
    ReportType.BALANCE_SHEET: ["期末余额", "期末数", "期末", "金额"],
    ReportType.INCOME_STATEMENT: [
        "本期金额",
        "本期数",
        "本年累计",
        "本年累计数",
        "累计金额",
        "累计数",
        "本期",
        "金额",
    ],
    ReportType.CASH_FLOW_STATEMENT: [
        "本期金额",
        "本期数",
        "本年累计",
        "本年累计数",
        "累计金额",
        "累计数",
        "本期",
        "金额",
    ],
}

_SECONDARY_COLUMN_CANDIDATES: dict[ReportType, list[str]] = {
    ReportType.BALANCE_SHEET: ["年初余额", "年初数", "期初余额", "期初数"],
    ReportType.INCOME_STATEMENT: ["上期金额", "上期数", "上期", "上年金额", "上年数", "上年累计"],
    ReportType.CASH_FLOW_STATEMENT: ["上期金额", "上期数", "上期", "上年金额", "上年数", "上年累计"],
}

_SUPPLEMENTARY_MARKER = "补充资料"
_YTD_PERIOD_RE = re.compile(r"^\d{4}年1-\d{1,2}月$")
_MONTH_PERIOD_RE = re.compile(r"^\d{4}年\d{1,2}月$")
_FULL_YEAR_RE = re.compile(r"^\d{4}年(1-12|12)月$")
_SERIAL_RE = re.compile(r"^\d{4,5}$")
_NUMERIC_RATIO = 0.3


def extract_items(raw: RawSheetData, report_type: ReportType) -> list[ReportItem]:
    """从原始工作表数据中提取 ReportItem 列表。

    Args:
        raw: 工作表原始数据
        report_type: 报表类型

    Returns:
        ReportItem 列表
    """
    name_column = _find_name_column(raw.headers)
    if name_column is None:
        logger.warning(f"工作表「{raw.name}」中未找到项目列，可用的列: {raw.headers}")
        return []

    primary, secondary = _pick_amount_columns(report_type, raw.headers, raw.rows, 0)
    if primary is None:
        logger.warning(f"工作表「{raw.name}」中未找到金额列，可用的列: {raw.headers}")
        return []

    items: list[ReportItem] = []
    seen_keys: set[str] = set()
    allow_supplementary = report_type == ReportType.CASH_FLOW_STATEMENT
    _extract_side(
        raw,
        name_column,
        primary,
        secondary,
        items,
        seen_keys,
        allow_supplementary,
    )

    if report_type == ReportType.BALANCE_SHEET:
        right_column = _find_right_name_column(raw.headers)
        if right_column is not None:
            right_primary, right_secondary = _pick_amount_columns(
                report_type, raw.headers, raw.rows, _column_index(raw.headers, right_column) + 1
            )
            if right_primary is not None:
                _extract_side(
                    raw,
                    right_column,
                    right_primary,
                    right_secondary,
                    items,
                    seen_keys,
                    allow_supplementary=False,
                )

    logger.info(f"  从工作表「{raw.name}」提取了 {len(items)} 个项目")
    return items


def _extract_side(
    raw: RawSheetData,
    name_column: str,
    primary: str,
    secondary: str | None,
    items: list[ReportItem],
    seen_keys: set[str],
    allow_supplementary: bool,
) -> None:
    """按指定的项目列与金额列提取一侧的报表项目。"""
    in_supplementary = False
    for row in raw.rows:
        item_name = row.get(name_column)
        if item_name is None:
            continue

        item_name_str = str(item_name).strip()
        if not item_name_str:
            continue

        row_num = _to_int(row.get("_row"))
        if row_num is None:
            row_num = 0

        if allow_supplementary and _SUPPLEMENTARY_MARKER in item_name_str:
            in_supplementary = True
            continue

        if in_supplementary:
            _extract_supplementary_row(
                item_name_str, row, primary, secondary, row_num, items, seen_keys
            )
            continue

        if _is_skip_row(item_name_str):
            continue

        _extract_item(
            item_name_str, row, primary, secondary, row_num, items, seen_keys
        )


def _extract_supplementary_row(
    item_name_str: str,
    row: dict[str, object],
    primary: str,
    secondary: str | None,
    row_num: int,
    items: list[ReportItem],
    seen_keys: set[str],
) -> None:
    """处理现金流量表补充资料区域的一行数据。"""
    if _is_skip_row(item_name_str):
        return
    cleaned = clean_name(item_name_str)
    key = get_supplementary_key(cleaned)
    if key is None:
        logger.debug(f"  补充资料中未映射的项目: 「{item_name_str}」(行{row_num})，跳过")
        return
    _append_item(
        cleaned, key, row, primary, secondary, row_num, items, seen_keys
    )


def _extract_item(
    item_name_str: str,
    row: dict[str, object],
    primary: str,
    secondary: str | None,
    row_num: int,
    items: list[ReportItem],
    seen_keys: set[str],
) -> None:
    """提取主表中的一个项目。"""
    key = get_key(item_name_str)
    if key is None:
        logger.debug(f"  未映射的项目: 「{item_name_str}」(行{row_num})，跳过")
        return
    _append_item(
        item_name_str, key, row, primary, secondary, row_num, items, seen_keys
    )


def _append_item(
    item_name_str: str,
    key: str,
    row: dict[str, object],
    primary: str,
    secondary: str | None,
    row_num: int,
    items: list[ReportItem],
    seen_keys: set[str],
) -> None:
    """读取金额并追加一个 ReportItem。"""
    if key in seen_keys:
        logger.warning(
            f"  重复项目: 「{item_name_str}」(key={key})，仅保留第一个出现(行{row_num})"
        )
        return

    amount = row.get(primary)
    if amount is None:
        logger.debug(f"  项目「{item_name_str}」的金额为空，跳过")
        return
    amount_float = parse_amount(amount)
    if amount_float is None:
        logger.warning(f"  项目「{item_name_str}」的金额无法转换为数字: {amount}，跳过")
        return

    beginning_amount = _read_optional_float(row, secondary)
    items.append(
        ReportItem(
            key=key,
            name=item_name_str,
            amount=amount_float,
            beginning_amount=beginning_amount,
            row=row_num,
            column=primary,
        )
    )
    seen_keys.add(key)


def _find_name_column(headers: list[str]) -> str | None:
    """查找项目名称列，未命中候选时回退到第一列。"""
    for candidate in _NAME_COLUMN_CANDIDATES:
        for header in headers:
            if _normalize(header) == candidate:
                return header
    return headers[0] if headers else None


def _find_right_name_column(headers: list[str]) -> str | None:
    """查找资产负债表的右侧项目列（负债和所有者权益栏）。"""
    for header in headers[1:]:
        normalized = _normalize(header)
        if "负债" in normalized and "权益" in normalized:
            return header
    return None


def _pick_amount_columns(
    report_type: ReportType,
    headers: list[str],
    rows: list[dict[str, object]],
    start_col: int,
) -> tuple[str | None, str | None]:
    """选择主金额列与次金额列（标准列名 -> 期间模式 -> 数值列回退）。"""
    primary_candidates = _PRIMARY_COLUMN_CANDIDATES.get(report_type, [])
    secondary_candidates = _SECONDARY_COLUMN_CANDIDATES.get(report_type, [])

    primary = _find_by_candidates(headers, primary_candidates, start_col)
    secondary = _find_by_candidates(headers, secondary_candidates, start_col)

    if primary is None and report_type != ReportType.BALANCE_SHEET:
        primary = _find_period_column(headers, start_col, primary=True)
        if primary is not None:
            secondary = _find_period_column(
                headers, _column_index(headers, primary) + 1, primary=False
            )

    if primary is None:
        numeric_columns = _numeric_columns(headers, rows, start_col)
        if numeric_columns:
            primary = numeric_columns[0]
            if secondary is None and len(numeric_columns) > 1:
                secondary = numeric_columns[1]

    return primary, secondary


def _find_by_candidates(
    headers: list[str],
    candidates: list[str],
    start_col: int,
) -> str | None:
    """按候选名精确/包含匹配查找列名。"""
    for candidate in candidates:
        for header in headers[start_col:]:
            normalized = _normalize(header)
            if normalized == candidate or candidate in normalized:
                return header
    return None


def _find_period_column(
    headers: list[str],
    start_col: int,
    primary: bool,
) -> str | None:
    """按期间列模式（2026年1-6月 / 46174 序列号等）查找列名。"""
    if primary:
        patterns = ((_YTD_PERIOD_RE,), (_MONTH_PERIOD_RE,), (_SERIAL_RE,))
    else:
        patterns = ((_FULL_YEAR_RE,), (_MONTH_PERIOD_RE,))
    for group in patterns:
        for header in headers[start_col:]:
            normalized = _normalize(header)
            if any(pattern.match(normalized) for pattern in group):
                return header
    return None


def _numeric_columns(
    headers: list[str],
    rows: list[dict[str, object]],
    start_col: int,
) -> list[str]:
    """返回数据行中数值占比超过阈值的列名（按列顺序）。"""
    result: list[str] = []
    threshold = max(2, int(len(rows) * _NUMERIC_RATIO))
    for header in headers[start_col:]:
        if _normalize(header) == "行次":
            continue
        numeric = 0
        for row in rows:
            value = row.get(header)
            if value is None:
                continue
            try:
                float(value)
            except (ValueError, TypeError):
                continue
            numeric += 1
        if numeric >= threshold:
            result.append(header)
    return result


def _column_index(headers: list[str], header: str) -> int:
    """返回列名在表头中的下标。"""
    for idx, candidate in enumerate(headers):
        if candidate == header:
            return idx
    return 0


def _read_optional_float(row: dict[str, object], column: str | None) -> float | None:
    """读取次金额列，不存在或不可解析时返回 None。"""
    if column is None:
        return None
    value = row.get(column)
    if value is None:
        return None
    return parse_amount(value)


def _is_skip_row(item_name_str: str) -> bool:
    """判断是否为分类行或备注行（应跳过）。"""
    return (
        item_name_str.endswith("：")
        or item_name_str.endswith(":")
        or item_name_str.startswith("注")
    )


def _normalize(value: str) -> str:
    """去除字符串中所有空白（含全角空格）。"""
    return re.sub(r"\s+", "", value)


def _to_int(value: object) -> int | None:
    """安全地将值转换为 int，失败返回 None。"""
    if value is None:
        return None
    if isinstance(value, (int, float, str)):
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    return None

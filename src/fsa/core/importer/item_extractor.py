"""报表项目提取器: 从 RawSheetData 提取 ReportItem 对象。

根据报表类型选择正确的金额列，将中文项目名映射为 key。
自动跳过分类行、备注行。补充资料区域提取 cf_notes_ 前缀项目。
支持双金额列（期末/期初、本期/上期）。
"""

from __future__ import annotations

# 前缀正则: 匹配 一、二、...十、 减：加： 等
import re

from loguru import logger

from fsa.core.importer.excel_reader import RawSheetData
from fsa.core.importer.name_mapper import get_key, get_supplementary_key
from fsa.core.models.report import ReportItem, ReportType

_PREFIX_RE = re.compile(r"^[一二三四五六七八九十]+、|^减[：:]|^加[：:]|^其中[：:]|^\s+")

# 报表类型 -> (主金额列候选, 次金额列候选)
# 主金额列: 期末余额/本期金额
# 次金额列: 年初余额/上期金额 (期初数)
_AMOUNT_COLUMN_CANDIDATES: dict[ReportType, tuple[list[str], list[str]]] = {
    ReportType.BALANCE_SHEET: (
        ["期末余额", "期末数", "期末"],
        ["年初余额", "年初数", "期初余额", "期初数"],
    ),
    ReportType.INCOME_STATEMENT: (
        ["本期金额", "本期数", "本期"],
        ["上期金额", "上期数", "上期"],
    ),
    ReportType.CASH_FLOW_STATEMENT: (
        ["本期金额", "本期数", "本期"],
        ["上期金额", "上期数", "上期"],
    ),
}

# 项目名称列候选（按优先级）
_NAME_COLUMN_CANDIDATES = ["项目", "项目名称", "科目", "科目名称"]

# 补充资料区域的标记文本
_SUPPLEMENTARY_MARKER = "补充资料"


def extract_items(
    raw: RawSheetData,
    report_type: ReportType,
) -> list[ReportItem]:
    """从原始工作表数据中提取 ReportItem 列表。

    处理流程:
    1. 查找项目列和金额列（主列 + 次列）
    2. 逐行处理:
       a. 跳过空行
       b. 跳过分类行（以：或:结尾）
       c. 跳过备注行（以"注"开头）
       d. 补充资料区域: 用 get_supplementary_key 映射，cf_notes_ 前缀
       e. 清洗名称并映射为 key
       f. 跳过未映射项
       g. 跳过重复项（仅保留首次出现，cf_notes_ keys 视为独立）
       h. 读取金额，跳过空值和非数字
       i. 读取次列金额（期初/上期），None 如果列不存在或单元格为空

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

    primary_column, secondary_column = _get_amount_columns(report_type, raw.headers)
    if primary_column is None:
        logger.warning(f"工作表「{raw.name}」中未找到金额列，可用的列: {raw.headers}")
        return []

    items: list[ReportItem] = []
    seen_keys: set[str] = set()
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

        # 检测补充资料区域开始
        if _SUPPLEMENTARY_MARKER in item_name_str:
            in_supplementary = True
            logger.debug(f"  进入补充资料区域: 「{item_name_str}」(行{row_num})")
            continue

        if in_supplementary:
            _handle_supplementary_row(
                item_name_str, row, primary_column,
                secondary_column, row_num, items, seen_keys,
            )
            continue

        # 跳过分类行（以：或:结尾）
        if item_name_str.endswith("：") or item_name_str.endswith(":"):
            continue

        # 跳过备注行
        if item_name_str.startswith("注"):
            continue

        _extract_item(
            item_name_str, row, primary_column, secondary_column,
            row_num, items, seen_keys, main_table=True,
        )

    logger.info(f"  从工作表「{raw.name}」提取了 {len(items)} 个项目")
    return items


def _handle_supplementary_row(
    item_name_str: str,
    row: dict[str, object],
    primary_column: str,
    secondary_column: str | None,
    row_num: int,
    items: list[ReportItem],
    seen_keys: set[str],
) -> None:
    """处理补充资料区域的一行数据。

    使用 get_supplementary_key 映射，不在映射表中的跳过。
    清洗前缀（减：、加：等）后再映射。
    """
    if item_name_str.endswith("：") or item_name_str.endswith(":"):
        return
    if item_name_str.startswith("注"):
        return

    # 清洗前缀后再映射
    cleaned = _PREFIX_RE.sub("", item_name_str).strip()
    key = get_supplementary_key(cleaned)
    if key is None:
        logger.debug(
            f"  补充资料中未映射的项目: 「{item_name_str}」(行{row_num})，跳过"
        )
        return

    _extract_item(
        cleaned, row, primary_column, secondary_column,
        row_num, items, seen_keys, main_table=False,
    )


def _extract_item(
    item_name_str: str,
    row: dict[str, object],
    primary_column: str,
    secondary_column: str | None,
    row_num: int,
    items: list[ReportItem],
    seen_keys: set[str],
    main_table: bool = True,
) -> None:
    """提取单个项目并添加到 items 列表。

    Args:
        item_name_str: 项目名称
        row: 数据行
        primary_column: 主金额列名
        secondary_column: 次金额列名（可为 None）
        row_num: 行号
        items: 目标列表
        seen_keys: 已见 key 集合
        main_table: 是否为主表区域（True 用 get_key，False 用 get_supplementary_key）
    """
    key = get_key(item_name_str) if main_table else get_supplementary_key(item_name_str)

    if key is None:
        if main_table:
            logger.debug(
                f"  未映射的项目: 「{item_name_str}」(行{row_num})，跳过"
            )
        return

    if key in seen_keys:
        logger.warning(
            f"  重复项目: 「{item_name_str}」(key={key})，"
            f"仅保留第一个出现(行{row_num})"
        )
        return

    amount = row.get(primary_column)
    if amount is None:
        logger.debug(f"  项目「{item_name_str}」的金额为空，跳过")
        return

    try:
        amount_float = float(amount)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        logger.warning(
            f"  项目「{item_name_str}」的金额无法转换为数字: {amount}，跳过"
        )
        return

    beginning_amount: float | None = None
    if secondary_column is not None:
        ba = row.get(secondary_column)
        if ba is not None:
            try:
                beginning_amount = float(ba)  # type: ignore[arg-type]
            except (ValueError, TypeError):
                beginning_amount = None

    item = ReportItem(
        key=key,
        name=item_name_str,
        amount=amount_float,
        beginning_amount=beginning_amount,
        row=row_num,
        column=primary_column,
    )
    items.append(item)
    seen_keys.add(key)


def _find_name_column(headers: list[str]) -> str | None:
    """查找项目名称列。

    按候选列表优先匹配，若都不匹配则取第一列。

    Args:
        headers: 列标题列表

    Returns:
        列名，未找到返回 None
    """
    for candidate in _NAME_COLUMN_CANDIDATES:
        for h in headers:
            if h == candidate:
                return h
    # 回退: 取第一列
    return headers[0] if headers else None


def _get_amount_columns(
    report_type: ReportType,
    headers: list[str],
) -> tuple[str | None, str | None]:
    """根据报表类型查找主金额列和次金额列。

    Args:
        report_type: 报表类型
        headers: 列标题列表

    Returns:
        (primary_column, secondary_column) 元组
    """
    candidates = _AMOUNT_COLUMN_CANDIDATES.get(report_type)
    if candidates is None:
        return None, None

    primary_candidates, secondary_candidates = candidates

    primary = _find_column(primary_candidates, headers)
    secondary = _find_column(secondary_candidates, headers)

    return primary, secondary


def _find_column(candidates: list[str], headers: list[str]) -> str | None:
    """在 headers 中查找第一个匹配的候选列名。"""
    for alt in candidates:
        if alt in headers:
            return alt
    return None


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

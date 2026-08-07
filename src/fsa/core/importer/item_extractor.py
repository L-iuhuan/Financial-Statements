"""报表项目提取器: 从 RawSheetData 提取 ReportItem 对象。

根据报表类型选择正确的金额列，将中文项目名映射为 key。
"""

from __future__ import annotations

from loguru import logger

from fsa.core.importer.excel_reader import RawSheetData
from fsa.core.importer.name_mapper import get_key
from fsa.core.models.report import ReportItem, ReportType

# 报表类型 -> 主要金额列名
_AMOUNT_COLUMN_MAP: dict[ReportType, str] = {
    ReportType.BALANCE_SHEET: "期末余额",
    ReportType.INCOME_STATEMENT: "本期金额",
    ReportType.CASH_FLOW_STATEMENT: "本期金额",
}


def extract_items(
    raw: RawSheetData,
    report_type: ReportType,
) -> list[ReportItem]:
    """从原始工作表数据中提取 ReportItem 列表。

    对于每个数据行：
    1. 读取"项目"列作为中文名称
    2. 通过 name_mapper 映射为 key
    3. 从未映射的项目跳过（记录日志）
    4. 从对应的金额列读取金额
    5. 金额为 None 则跳过

    Args:
        raw: 工作表原始数据
        report_type: 报表类型

    Returns:
        ReportItem 列表
    """
    amount_column = _get_amount_column(report_type, raw.headers)
    if amount_column is None:
        logger.warning(f"工作表「{raw.name}」中未找到金额列，可用的列: {raw.headers}")
        return []

    items: list[ReportItem] = []
    seen_keys: set[str] = set()

    for row in raw.rows:
        item_name = row.get("项目")
        if item_name is None:
            continue

        item_name_str = str(item_name).strip()
        if not item_name_str:
            continue

        key = get_key(item_name_str)
        if key is None:
            logger.debug(f"  未映射的项目: 「{item_name_str}」(行{row['_row']})，跳过")
            continue

        if key in seen_keys:
            logger.warning(f"  重复项目: 「{item_name_str}」(key={key})，仅保留第一个出现(行{row['_row']})")
            continue

        amount = row.get(amount_column)
        if amount is None:
            logger.debug(f"  项目「{item_name_str}」的金额为空，跳过")
            continue

        try:
            amount_float = float(amount)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            logger.warning(f"  项目「{item_name_str}」的金额无法转换为数字: {amount}，跳过")
            continue

        row_num = _to_int(row["_row"])
        if row_num is None:
            row_num = 0

        item = ReportItem(
            key=key,
            name=item_name_str,
            amount=amount_float,
            row=row_num,
            column=amount_column,
        )
        items.append(item)
        seen_keys.add(key)

    logger.info(f"  从工作表「{raw.name}」提取了 {len(items)} 个项目")
    return items


def _get_amount_column(
    report_type: ReportType,
    headers: list[str],
) -> str | None:
    """根据报表类型查找合适的金额列。

    优先使用映射表中的默认列名，若不存在则在表头中查找。

    Args:
        report_type: 报表类型
        headers: 列标题列表

    Returns:
        金额列名，未找到返回 None
    """
    default = _AMOUNT_COLUMN_MAP.get(report_type, "")
    if default and default in headers:
        return default

    # 备选查找: 资产负债表用"期末余额"或"期末数"
    if report_type == ReportType.BALANCE_SHEET:
        for alt in ["期末余额", "期末数", "期末"]:
            if alt in headers:
                return alt

    # 利润表/现金流量表用"本期金额"或"本期数"
    for alt in ["本期金额", "本期数", "本期"]:
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

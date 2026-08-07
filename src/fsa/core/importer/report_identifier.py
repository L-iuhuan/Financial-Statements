"""报表类型识别器: 从工作表名和内容识别报表类型。

识别策略:
1. 优先按工作表名匹配（精确包含关键词）
2. 其次按工作表内容匹配（查找特征科目）
"""

from __future__ import annotations

from loguru import logger

from fsa.core.importer.excel_reader import RawSheetData
from fsa.core.models.report import ReportType

# 工作表名关键词 -> 报表类型
_SHEET_NAME_PATTERNS: dict[str, ReportType] = {
    "资产负债表": ReportType.BALANCE_SHEET,
    "Balance Sheet": ReportType.BALANCE_SHEET,
    "利润表": ReportType.INCOME_STATEMENT,
    "Income Statement": ReportType.INCOME_STATEMENT,
    "现金流量表": ReportType.CASH_FLOW_STATEMENT,
    "Cash Flow": ReportType.CASH_FLOW_STATEMENT,
}

# 内容关键词 -> 报表类型（当工作表名无法识别时使用）
_CONTENT_KEYWORDS: dict[str, ReportType] = {
    "资产总计": ReportType.BALANCE_SHEET,
    "负债合计": ReportType.BALANCE_SHEET,
    "营业收入": ReportType.INCOME_STATEMENT,
    "营业利润": ReportType.INCOME_STATEMENT,
    "经营活动产生的现金流量净额": ReportType.CASH_FLOW_STATEMENT,
    "投资活动产生的现金流量净额": ReportType.CASH_FLOW_STATEMENT,
}


def identify_reports(
    data: dict[str, RawSheetData],
) -> list[tuple[str, ReportType]]:
    """从原始工作表数据中识别报表类型。

    对每个工作表，先尝试按名称识别，再按内容识别。

    Args:
        data: 工作表名 -> RawSheetData 的字典

    Returns:
        (工作表名, ReportType) 的列表，仅包含成功识别的报表
    """
    results: list[tuple[str, ReportType]] = []

    for sheet_name, raw in data.items():
        report_type = _identify_by_name(sheet_name)
        if report_type is None:
            report_type = _identify_by_content(raw)

        if report_type is not None:
            results.append((sheet_name, report_type))
            logger.info(f"  识别报表: 「{sheet_name}」 -> {report_type.value}")
        else:
            logger.debug(f"  跳过未识别的工作表: 「{sheet_name}」")

    return results


def _identify_by_name(sheet_name: str) -> ReportType | None:
    """按工作表名识别报表类型。

    Args:
        sheet_name: 工作表名

    Returns:
        ReportType 或 None
    """
    for pattern, report_type in _SHEET_NAME_PATTERNS.items():
        if pattern.lower() in sheet_name.lower():
            return report_type
    return None


def _identify_by_content(raw: RawSheetData) -> ReportType | None:
    """按工作表内容识别报表类型。

    扫描数据行中的项目名称，匹配特征关键词。

    Args:
        raw: 工作表原始数据

    Returns:
        ReportType 或 None
    """
    for row in raw.rows:
        item_name = row.get("项目")
        if item_name is None:
            continue
        item_name_str = str(item_name).strip()
        if item_name_str in _CONTENT_KEYWORDS:
            return _CONTENT_KEYWORDS[item_name_str]
    return None

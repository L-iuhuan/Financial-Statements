"""附表 2 明细导入器: 科目余额表 / 序时账 / 现金流量明细。

按表头特征识别工作表类型（不依赖工作表名），并按"本月 / 1-本月"
分别归入当前期间与累计数据集。
"""

from __future__ import annotations

import math
import re

from loguru import logger

from fsa.core.importer.excel_reader import RawSheetData, read_excel
from fsa.core.models.detail import (
    CashFlowDetailRow,
    DetailDataset,
    InternalCashFlowRow,
    JournalRow,
    ReclassificationRow,
    RelatedPartyPurchaseRow,
    SalesDetailRow,
    TrialBalanceRow,
)

_CUMULATIVE_KEYWORDS = ("1-本月", "1- 本月", "本年累计")


class DetailImporter:
    """明细数据导入服务。"""

    def __init__(self, period: str = "") -> None:
        self.period = period

    def import_file(self, file_path: str) -> DetailDataset:
        """读取文件并解析为 DetailDataset（含 Excel COM 自动回退）。"""
        raw_data = read_excel(file_path)
        dataset = DetailDataset(source_file=str(file_path), period=self.period)

        for sheet_name, raw in raw_data.items():
            if _is_trial_balance(raw.headers):
                self._collect_trial_balance(dataset, sheet_name, raw)
            elif _is_journal(raw.headers):
                self._collect_journal(dataset, sheet_name, raw)
            elif _is_cash_flow_detail(raw.headers):
                self._collect_cash_flow_detail(dataset, sheet_name, raw)
            elif _is_reclassification(raw.headers):
                self._collect_reclassification(dataset, raw)
            elif _is_related_party_purchase(raw.headers):
                self._collect_related_party_purchase(dataset, raw)
            elif _is_sales_detail(raw.headers):
                self._collect_sales_detail(dataset, raw)
            elif _is_internal_cash_flow(raw.headers):
                self._collect_internal_cash_flow(dataset, raw)

        logger.info(
            f"明细导入完成: 余额表 {len(dataset.trial_balance)} 行, "
            f"序时账 {len(dataset.journal)} 行, "
            f"现金流明细 {len(dataset.cash_flow_detail)} 行"
        )
        return dataset

    def _collect_trial_balance(
        self, dataset: DetailDataset, sheet_name: str, raw: RawSheetData
    ) -> None:
        """解析科目余额表工作表。"""
        rows = [
            _parse_trial_balance_row(raw.headers, row)
            for row in raw.rows
        ]
        rows = [r for r in rows if r is not None]
        target = (
            dataset.trial_balance
            if _is_cumulative(sheet_name)
            else dataset.trial_balance_current
        )
        target.extend(rows)

    def _collect_journal(
        self, dataset: DetailDataset, sheet_name: str, raw: RawSheetData
    ) -> None:
        """解析序时账工作表。"""
        if not _is_cumulative(sheet_name):
            return
        rows = [_parse_journal_row(raw.headers, row) for row in raw.rows]
        dataset.journal.extend([r for r in rows if r is not None])

    def _collect_cash_flow_detail(
        self, dataset: DetailDataset, sheet_name: str, raw: RawSheetData
    ) -> None:
        """解析现金流量明细工作表。"""
        if not _is_cumulative(sheet_name):
            return
        rows = [_parse_cash_flow_row(raw.headers, row) for row in raw.rows]
        dataset.cash_flow_detail.extend([r for r in rows if r is not None])

    def _collect_reclassification(
        self, dataset: DetailDataset, raw: RawSheetData
    ) -> None:
        """解析往来重分类明细工作表。"""
        rows = [_parse_reclassification_row(raw.headers, row) for row in raw.rows]
        dataset.reclassifications.extend([r for r in rows if r is not None])

    def _collect_related_party_purchase(
        self, dataset: DetailDataset, raw: RawSheetData
    ) -> None:
        """解析关联方采购明细工作表。"""
        rows = [_parse_purchase_row(raw.headers, row) for row in raw.rows]
        dataset.related_party_purchases.extend([r for r in rows if r is not None])

    def _collect_sales_detail(
        self, dataset: DetailDataset, raw: RawSheetData
    ) -> None:
        """解析销售收入成本明细工作表。"""
        rows = [_parse_sales_row(raw.headers, row) for row in raw.rows]
        dataset.sales_details.extend([r for r in rows if r is not None])

    def _collect_internal_cash_flow(
        self, dataset: DetailDataset, raw: RawSheetData
    ) -> None:
        """解析内部交易现金流量明细工作表。"""
        rows = [_parse_internal_cash_flow_row(raw.headers, row) for row in raw.rows]
        dataset.internal_cash_flows.extend([r for r in rows if r is not None])


def _is_trial_balance(headers: list[str]) -> bool:
    """按表头判断是否为科目余额表。"""
    joined = "".join(_normalize(h) for h in headers)
    return "科目编码" in joined and "余额借方" in joined


def _is_journal(headers: list[str]) -> bool:
    """按表头判断是否为序时账。"""
    joined = "".join(_normalize(h) for h in headers)
    return (
        "科目编码" in joined
        and "凭证号" in joined
        and "摘要" in joined
        and "方向" in joined
    )


def _is_cash_flow_detail(headers: list[str]) -> bool:
    """按表头判断是否为现金流量明细（区别于现金流量表主表）。"""
    joined = "".join(_normalize(h) for h in headers)
    return "现金流量项目" in joined and "方向" in joined


def _is_reclassification(headers: list[str]) -> bool:
    """按表头判断是否为往来重分类明细。"""
    joined = "".join(_normalize(h) for h in headers)
    return "重分类后科目" in joined and "账面余额" in joined


def _is_related_party_purchase(headers: list[str]) -> bool:
    """按表头判断是否为关联方采购明细。"""
    joined = "".join(_normalize(h) for h in headers)
    return "总采购金额" in joined and "对方单位名称" in joined


def _is_sales_detail(headers: list[str]) -> bool:
    """按表头判断是否为销售收入成本明细。"""
    joined = "".join(_normalize(h) for h in headers)
    return "销售收入金额" in joined and "销售成本金额" in joined


def _is_internal_cash_flow(headers: list[str]) -> bool:
    """按表头判断是否为内部交易现金流量明细。"""
    joined = "".join(_normalize(h) for h in headers)
    return "统计单位名称" in joined and "现金流量项目" in joined


def _is_cumulative(sheet_name: str) -> bool:
    """判断工作表是否为累计口径（1-本月）。"""
    return any(keyword in sheet_name for keyword in _CUMULATIVE_KEYWORDS)


def _parse_trial_balance_row(
    headers: list[str], row: dict[str, object]
) -> TrialBalanceRow | None:
    """解析科目余额表的一行。"""
    code = _text(row, _find_col(headers, "科目编码"))
    name = _text(row, _find_col(headers, "科目名称"))
    if not code or not name:
        return None
    return TrialBalanceRow(
        account_code=code,
        account_name=name,
        beginning_debit=_number(row, _find_col(headers, "期初余额借方")),
        beginning_credit=_number(row, _find_col(headers, "期初余额贷方")),
        period_debit=_number(row, _find_col(headers, "本期发生借方")),
        period_credit=_number(row, _find_col(headers, "本期发生贷方")),
        ending_debit=_number(row, _find_col(headers, "期末余额借方")),
        ending_credit=_number(row, _find_col(headers, "期末余额贷方")),
        row=_to_int(row.get("_row")),
    )


def _parse_journal_row(
    headers: list[str], row: dict[str, object]
) -> JournalRow | None:
    """解析序时账的一行。"""
    voucher = _text(row, _find_col(headers, "凭证号"))
    direction = _text(row, _find_col(headers, "方向"))
    if not voucher or direction not in ("借", "贷"):
        return None
    return JournalRow(
        date=_text(row, _find_col(headers, "日期")),
        voucher_no=voucher,
        parent_account=_text(row, _find_col(headers, "上级科目")),
        account_code=_text(row, _find_col(headers, "科目编码")),
        account_name=_text(row, _find_col(headers, "科目名称")),
        summary=_text(row, _find_col(headers, "摘要")),
        direction=direction,
        amount=_number(row, _find_amount_col(headers)),
        row=_to_int(row.get("_row")),
    )


def _parse_cash_flow_row(
    headers: list[str], row: dict[str, object]
) -> CashFlowDetailRow | None:
    """解析现金流量明细的一行。"""
    project = _text(row, _find_col(headers, "现金流量项目"))
    direction = _text(row, _find_col(headers, "方向"))
    if not project or direction not in ("流入", "流出"):
        return None
    return CashFlowDetailRow(
        voucher_no=_text(row, _find_col(headers, "凭证号")),
        project=project,
        summary=_text(row, _find_col(headers, "摘要")),
        direction=direction,
        amount=_number(row, _find_amount_col(headers)),
        month=_to_int(row.get(_find_col(headers, "年月"))),
        day=_to_int(row.get(_find_col(headers, "年日"))),
        row=_to_int(row.get("_row")),
    )


def _parse_reclassification_row(
    headers: list[str], row: dict[str, object]
) -> ReclassificationRow | None:
    """解析往来重分类明细的一行。"""
    original = _text(row, _find_col(headers, "账面对应往来科目"))
    if not original:
        return None
    return ReclassificationRow(
        original_account=original,
        counterparty=_text(row, _find_col(headers, "客户/供应商")),
        book_amount=_number(row, _find_col(headers, "账面余额")),
        reclassified_account=_text(row, _find_col(headers, "重分类后科目")),
        reclassified_amount=_number(row, _find_col(headers, "重分类后金额")),
        invoiced_amount=_number(row, _find_col(headers, "开票金额")),
        accrued_amount=_number(row, _find_col(headers, "暂估金额")),
        is_related_party=_text(row, _find_col(headers, "是否合并范围内关联方")),
        note=_text(row, _find_col(headers, "备注")),
        row=_to_int(row.get("_row")),
    )


def _parse_purchase_row(
    headers: list[str], row: dict[str, object]
) -> RelatedPartyPurchaseRow | None:
    """解析关联方采购明细的一行。"""
    buyer = _text(row, _find_col(headers, "填表单位-购买方"))
    counterparty = _text(row, _find_col(headers, "对方单位名称"))
    if not buyer and not counterparty:
        return None
    return RelatedPartyPurchaseRow(
        buyer=buyer,
        counterparty=counterparty,
        payment_nature=_text(row, _find_col(headers, "款项性质")),
        total_amount=_number(row, _find_exact_col(headers, "总采购金额")),
        supply_chain=_number(row, _find_col(headers, "供应链采购")),
        mold=_number(row, _find_col(headers, "模具采购")),
        inventory=_number(row, _find_col(headers, "结存存货")),
        main_cost=_number(row, _find_col(headers, "主营业务成本")),
        other_cost=_number(row, _find_col(headers, "其他业务成本")),
        rnd_expense=_number(row, _find_col(headers, "研发费用")),
        admin_expense=_number(row, _find_col(headers, "管理费用")),
        selling_expense=_number(row, _find_col(headers, "销售费用")),
        other=_number(row, _find_exact_col(headers, "其他")),
        difference_reason=_text(row, _find_exact_col(headers, "差异原因")),
        row=_to_int(row.get("_row")),
    )


def _parse_sales_row(
    headers: list[str], row: dict[str, object]
) -> SalesDetailRow | None:
    """解析销售收入成本明细的一行。"""
    revenue = _number(row, _find_col(headers, "销售收入金额"))
    cost = _number(row, _find_col(headers, "销售成本金额"))
    if revenue == 0.0 and cost == 0.0:
        return None
    margin_value = row.get(_find_col(headers, "销售毛利率"))
    margin: float | None = _optional_number(margin_value)
    return SalesDetailRow(
        year=_to_int(row.get(_find_exact_col(headers, "年"))),
        month=_to_int(row.get(_find_exact_col(headers, "月"))),
        entity=_text(row, _find_col(headers, "归属主体")),
        customer=_text(row, _find_col(headers, "客户名称")),
        revenue_type=_text(row, _find_col(headers, "收入类型")),
        revenue_amount=revenue,
        cost_amount=cost,
        direct_material=_number(row, _find_exact_col(headers, "直接材料")),
        processing=_number(row, _find_exact_col(headers, "加工费")),
        direct_labor=_number(row, _find_exact_col(headers, "直接人工")),
        manufacturing=_number(row, _find_exact_col(headers, "制造费")),
        gross_margin=margin,
        row=_to_int(row.get("_row")),
    )


def _parse_internal_cash_flow_row(
    headers: list[str], row: dict[str, object]
) -> InternalCashFlowRow | None:
    """解析内部交易现金流量明细的一行。"""
    project = _text(row, _find_col(headers, "现金流量项目"))
    amount = _number(row, _find_exact_col(headers, "发生额"))
    if not project or amount == 0.0:
        return None
    return InternalCashFlowRow(
        month=_to_int(row.get(_find_col(headers, "月份"))),
        entity=_text(row, _find_col(headers, "统计单位名称")),
        counterparty=_text(row, _find_col(headers, "对方单位名称")),
        payment_nature=_text(row, _find_col(headers, "款项性质")),
        project=project,
        amount=amount,
        row=_to_int(row.get("_row")),
    )


def _find_col(headers: list[str], keyword: str) -> str | None:
    """按关键字（去空白后包含匹配）查找列名。"""
    normalized_keyword = _normalize(keyword)
    for header in headers:
        if normalized_keyword in _normalize(header):
            return header
    return None


def _find_exact_col(headers: list[str], name: str) -> str | None:
    """按去空白后的精确名称查找列名（避免"其他"误命中"其他业务成本"）。"""
    normalized_name = _normalize(name)
    for header in headers:
        if _normalize(header) == normalized_name:
            return header
    return None


def _find_amount_col(headers: list[str]) -> str | None:
    """优先取精确的「金额」列，避免与「原币」混淆。"""
    for header in headers:
        if _normalize(header) == "金额":
            return header
    return _find_col(headers, "金额")


def _text(row: dict[str, object], column: str | None) -> str:
    """读取单元格文本，缺失返回空字符串。"""
    if column is None:
        return ""
    value = row.get(column)
    return "" if value is None else str(value).strip()


def _number(row: dict[str, object], column: str | None) -> float:
    """读取单元格数值，缺失或不可解析返回 0.0。"""
    value = row.get(column) if column is not None else None
    if value is None:
        return 0.0
    try:
        result = float(value)
    except (ValueError, TypeError):
        return 0.0
    if math.isnan(result):
        return 0.0
    return result


def _optional_number(value: object) -> float | None:
    """安全转为 float，不可解析返回 None。"""
    if value is None:
        return None
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    if math.isnan(result):
        return None
    return result


def _to_int(value: object) -> int:
    """安全转为 int，失败返回 0。"""
    if value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _normalize(value: str) -> str:
    """去除所有空白（含全角空格）。"""
    return re.sub(r"\s+", "", value)

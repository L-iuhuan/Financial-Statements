"""明细行解析工具: 将原始工作表行转换为明细数据模型对象。

从 detail_importer 中拆出，避免单文件超限。
每个解析函数按表头列名读取一行 dict，返回对应数据模型对象；
无法识别的行返回 None（由调用方过滤）。
金额解析统一走 amount_parser，兼容千分位/括号负数/占位符。
"""

from __future__ import annotations

import re

from fsa.core.importer.amount_parser import parse_amount
from fsa.core.models.detail import (
    CashFlowDetailRow,
    InternalCashFlowRow,
    JournalRow,
    ReclassificationRow,
    RelatedPartyPurchaseRow,
    SalesDetailRow,
    TrialBalanceRow,
)


def parse_trial_balance_row(
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


def parse_journal_row(headers: list[str], row: dict[str, object]) -> JournalRow | None:
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


def parse_cash_flow_row(
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


def parse_reclassification_row(
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


def parse_purchase_row(
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


def parse_sales_row(
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


def parse_internal_cash_flow_row(
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
    result = parse_amount(value)
    return 0.0 if result is None else result


def _optional_number(value: object) -> float | None:
    """安全转为 float，不可解析返回 None。"""
    if value is None:
        return None
    return parse_amount(value)


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

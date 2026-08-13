"""附表 4/5/6 检查：关联方采购、销售收入成本、内部交易现金流。"""

from __future__ import annotations

from collections import defaultdict

from fsa.core.importer.name_mapper import clean_name
from fsa.core.models.detail import DetailDataset
from fsa.core.models.report import Report, ReportType
from fsa.core.models.result import ValidationResult
from fsa.core.models.rule import Severity

# 内部现金流项目名 -> 主表现金流量表项目名（用词差异）
_INTERNAL_PROJECT_ALIASES: dict[str, str] = {
    "收到的其他与经营活动的现金": "收到其他与经营活动有关的现金",
    "支付的其他与经营活动的现金": "支付其他与经营活动有关的现金",
}


def check_related_party_purchase_breakdown(
    dataset: DetailDataset, tolerance: float
) -> list[ValidationResult]:
    """核对关联方采购总金额与成本/费用分类合计。"""
    mismatches: list[str] = []
    for row in dataset.related_party_purchases:
        breakdown = (
            row.supply_chain
            + row.mold
            + row.inventory
            + row.main_cost
            + row.other_cost
            + row.rnd_expense
            + row.admin_expense
            + row.selling_expense
            + row.other
        )
        diff = row.total_amount - breakdown
        if abs(diff) > tolerance:
            mismatches.append(
                f"行{row.row}「{row.counterparty}」总采购 {row.total_amount:,.2f} "
                f"vs 分类合计 {breakdown:,.2f}（差额 {diff:,.2f}）"
            )

    passed = not mismatches
    message = (
        f"关联方采购分类合计: 校验通过（共 {len(dataset.related_party_purchases)} 行）"
        if passed
        else f"关联方采购分类合计: {len(mismatches)} 行不一致。" + "；".join(mismatches[:5])
    )
    return [
        ValidationResult(
            rule_id="RP-001",
            rule_name="关联方采购分类合计",
            passed=passed,
            severity=Severity.ERROR if not passed else Severity.ERROR,
            left_value=0.0,
            right_value=0.0,
            diff=float(len(mismatches)),
            tolerance=tolerance,
            formula="总采购金额 == 成本/费用分类合计",
            message=message,
            category="L2-明细勾稽",
        )
    ]


def check_sales_detail_consistency(
    dataset: DetailDataset, tolerance: float
) -> list[ValidationResult]:
    """核对销售收入成本明细的成本构成与毛利率。"""
    mismatches: list[str] = []
    for row in dataset.sales_details:
        cost_parts = (
            row.direct_material + row.processing + row.direct_labor + row.manufacturing
        )
        # 成本构成列未填报时跳过构成核对，仅核对毛利率（宁可漏报不可误报）
        cost_ok = cost_parts == 0.0 or abs(cost_parts - row.cost_amount) <= tolerance
        margin_ok = True
        if row.gross_margin is not None and row.revenue_amount > 0:
            expected = (row.revenue_amount - row.cost_amount) / row.revenue_amount
            margin_ok = abs(row.gross_margin - expected) <= 0.01
        if not cost_ok or not margin_ok:
            mismatches.append(
                f"行{row.row}「{row.customer}」成本构成 {cost_parts:,.2f} "
                f"/ 成本 {row.cost_amount:,.2f}"
            )

    passed = not mismatches
    message = (
        f"销售收入成本明细一致性: 校验通过（共 {len(dataset.sales_details)} 行）"
        if passed
        else f"销售收入成本明细一致性: {len(mismatches)} 行异常。" + "；".join(mismatches[:5])
    )
    return [
        ValidationResult(
            rule_id="SAL-001",
            rule_name="销售收入成本明细一致性",
            passed=passed,
            severity=Severity.ERROR if not passed else Severity.ERROR,
            left_value=0.0,
            right_value=0.0,
            diff=float(len(mismatches)),
            tolerance=tolerance,
            formula="成本构成合计==销售成本; 毛利率==(收入-成本)/收入",
            message=message,
            category="L2-明细勾稽",
        )
    ]


def check_sales_vs_income_statement(
    dataset: DetailDataset,
    reports: dict[ReportType, Report],
    tolerance: float,
) -> list[ValidationResult]:
    """核对销售收入成本明细合计与利润表营业收入/营业成本。"""
    report = reports.get(ReportType.INCOME_STATEMENT)
    if report is None:
        return []
    statement = {item.key: item.amount for item in report.items}
    revenue = sum(row.revenue_amount for row in dataset.sales_details)
    cost = sum(row.cost_amount for row in dataset.sales_details)

    results: list[ValidationResult] = []
    for key, name, amount in (
        ("revenue", "营业收入", revenue),
        ("operating_cost", "营业成本", cost),
    ):
        actual = statement.get(key)
        if actual is None:
            continue
        diff = amount - actual
        passed = abs(diff) <= tolerance
        results.append(
            ValidationResult(
                rule_id="SAL-002",
                rule_name="销售收入成本明细=利润表",
                passed=passed,
                severity=Severity.ERROR if not passed else Severity.ERROR,
                left_value=amount,
                right_value=actual,
                diff=diff,
                tolerance=tolerance,
                formula="明细合计 == 利润表项目",
                message=(
                    f"销售明细{name}合计 {amount:,.2f} vs 利润表 {actual:,.2f}: "
                    f"{'一致' if passed else f'差额 {diff:,.2f}'}"
                ),
                category="L2-明细勾稽",
            )
        )
    return results


def check_internal_cash_flow_vs_statement(
    dataset: DetailDataset,
    reports: dict[ReportType, Report],
    tolerance: float,
) -> list[ValidationResult]:
    """核对内部交易现金流各项目合计不超过主表现金流量表对应项目。"""
    report = reports.get(ReportType.CASH_FLOW_STATEMENT)
    if report is None:
        return []
    statement = {clean_name(item.name): item.amount for item in report.items}

    sums: dict[str, float] = defaultdict(float)
    for row in dataset.internal_cash_flows:
        key = clean_name(row.project)
        alias = _INTERNAL_PROJECT_ALIASES.get(key, key)
        sums[alias] += row.amount

    results: list[ValidationResult] = []
    for project, amount in sums.items():
        statement_amount = statement.get(project)
        if statement_amount is None:
            continue
        passed = amount <= statement_amount + tolerance
        results.append(
            ValidationResult(
                rule_id="ICF-001",
                rule_name="内部现金流≤主表现金流量",
                passed=passed,
                severity=Severity.WARNING,
                left_value=amount,
                right_value=statement_amount,
                diff=amount - statement_amount,
                tolerance=tolerance,
                formula="内部项目合计 <= 主表项目",
                message=(
                    f"内部现金流「{project}」{amount:,.2f} vs 主表 {statement_amount:,.2f}: "
                    f"{'未超主表' if passed else f'超出 {amount - statement_amount:,.2f}'}"
                ),
                category="L2-明细勾稽",
            )
        )
    return results

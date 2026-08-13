"""往来重分类检查（附表 3）。"""

from __future__ import annotations

from collections import defaultdict

from fsa.core.importer.name_mapper import clean_name
from fsa.core.models.detail import DetailDataset
from fsa.core.models.report import Report, ReportType
from fsa.core.models.result import ValidationResult
from fsa.core.models.rule import Severity

# 负数重分类的目标科目（含企业常用别名）
_RECLASS_PAIRS: dict[str, tuple[str, ...]] = {
    "应收账款": ("预收款项", "预收账款"),
    "预收账款": ("应收账款",),
    "应付账款": ("预付款项", "预付账款"),
    "预付账款": ("应付账款",),
    "其他应收款": ("其他应付款",),
    "其他应付款": ("其他应收款",),
}

# 报表项目 key -> 重分类后科目名称集合
_BALANCE_SHEET_ACCOUNTS: dict[str, tuple[str, ...]] = {
    "accounts_receivable": ("应收账款",),
    "advance_from_customers": ("预收款项", "预收账款"),
    "accounts_payable": ("应付账款",),
    "prepayments": ("预付款项", "预付账款"),
    "other_receivable": ("其他应收款",),
    "other_payable": ("其他应付款",),
}


def check_reclassification_rules(
    dataset: DetailDataset, tolerance: float
) -> list[ValidationResult]:
    """核对负数重分类规则：负数转正、科目落到对应往来科目。"""
    mismatches: list[str] = []
    for row in dataset.reclassifications:
        book = row.book_amount
        reclassified = row.reclassified_amount
        if book < -tolerance:
            amount_ok = abs(reclassified + book) <= tolerance
            account_ok = row.reclassified_account in _RECLASS_PAIRS.get(
                row.original_account, ()
            )
        elif book > tolerance:
            amount_ok = abs(reclassified - book) <= tolerance
            account_ok = row.reclassified_account == row.original_account
        else:
            continue
        if not amount_ok or not account_ok:
            mismatches.append(
                f"行{row.row}「{row.counterparty}」账面 {book:,.2f} → "
                f"{row.reclassified_account} {reclassified:,.2f}"
            )

    passed = not mismatches
    message = (
        f"往来重分类规则: 校验通过（共 {len(dataset.reclassifications)} 行）"
        if passed
        else f"往来重分类规则: {len(mismatches)} 行与重分类规则不符。"
        + "；".join(mismatches[:5])
    )
    return [
        ValidationResult(
            rule_id="RC-001",
            rule_name="往来重分类规则",
            passed=passed,
            severity=Severity.ERROR if not passed else Severity.ERROR,
            left_value=0.0,
            right_value=0.0,
            diff=float(len(mismatches)),
            tolerance=tolerance,
            formula="负数重分类转正 + 科目对应",
            message=message,
            category="L2-明细勾稽",
        )
    ]


def check_reclassification_vs_balance_sheet(
    dataset: DetailDataset,
    reports: dict[ReportType, Report],
    tolerance: float,
) -> list[ValidationResult]:
    """核对重分类后各往来科目合计与资产负债表项目。"""
    report = reports.get(ReportType.BALANCE_SHEET)
    if report is None:
        return [
            ValidationResult(
                rule_id="RC-002",
                rule_name="重分类后科目=资产负债表",
                passed=True,
                severity=Severity.INFO,
                left_value=0.0,
                right_value=0.0,
                diff=0.0,
                tolerance=tolerance,
                formula="",
                message="重分类后科目=资产负债表: 跳过 - 缺少资产负债表",
                skipped=True,
                category="L2-明细勾稽",
            )
        ]

    statement = {item.key: item.amount for item in report.items}
    sums: dict[str, float] = defaultdict(float)
    for row in dataset.reclassifications:
        account = clean_name(row.reclassified_account)
        for key, names in _BALANCE_SHEET_ACCOUNTS.items():
            if account in names:
                sums[key] += row.reclassified_amount
                break

    results: list[ValidationResult] = []
    for key in _BALANCE_SHEET_ACCOUNTS:
        expected = sums.get(key, 0.0)
        actual = statement.get(key)
        if actual is None:
            continue
        diff = expected - actual
        passed = abs(diff) <= tolerance
        results.append(
            ValidationResult(
                rule_id="RC-002",
                rule_name="重分类后科目=资产负债表",
                passed=passed,
                severity=Severity.ERROR if not passed else Severity.ERROR,
                left_value=expected,
                right_value=actual,
                diff=diff,
                tolerance=tolerance,
                formula="重分类后科目合计 == 报表项目",
                message=(
                    f"重分类后「{key}」合计 {expected:,.2f} vs 报表 {actual:,.2f}: "
                    f"{'一致' if passed else f'差额 {diff:,.2f}（差异可能来自坏账准备等报表调整，需人工确认）'}"
                ),
                category="L2-明细勾稽",
            )
        )
    return results

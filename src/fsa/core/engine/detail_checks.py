"""明细层勾稽检查（L2）: 凭证平衡、现金流明细核对、余额表与主表勾稽。

每个检查函数接收 DetailDataset 与主表 Report，返回 ValidationResult 列表，
结果可追溯（凭证号/科目/差额），遵循"宁可漏报不可误报"原则。
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import cast

from fsa.core.importer.name_mapper import clean_name
from fsa.core.models.detail import DetailDataset
from fsa.core.models.report import Report, ReportType
from fsa.core.models.result import ValidationResult
from fsa.core.models.rule import Severity

# 现金流量明细项目名 -> 主表项目名（企业导出与准则列报用词差异）
CF_PROJECT_ALIASES: dict[str, str] = {
    "收到的其他与经营活动的现金": "收到其他与经营活动有关的现金",
    "支付的其他与经营活动的现金": "支付其他与经营活动有关的现金",
    "支付的与其他经营活动有关的现金": "支付其他与经营活动有关的现金",
    "投资所支付的现金": "投资支付的现金",
    "收回投资所收到的现金": "收回投资收到的现金",
    "取得投资收益所收到的现金": "取得投资收益收到的现金",
    "购建固定资产、无形资产和其他长期资产所支付的现金": "购建固定资产、无形资产和其他长期资产支付的现金",
}


def check_journal_voucher_balance(
    dataset: DetailDataset, tolerance: float
) -> list[ValidationResult]:
    """逐凭证核对序时账借贷平衡。"""
    debit: dict[str, float] = defaultdict(float)
    credit: dict[str, float] = defaultdict(float)
    for row in dataset.journal:
        if row.direction == "借":
            debit[row.voucher_no] += row.amount
        elif row.direction == "贷":
            credit[row.voucher_no] += row.amount

    mismatches = [
        (voucher, debit[voucher] - credit[voucher])
        for voucher in debit.keys() | credit.keys()
        if abs(debit[voucher] - credit[voucher]) > tolerance
    ]
    passed = not mismatches
    detail = "；".join(
        f"凭证{voucher} 借{debit[voucher]:,.2f}/贷{credit[voucher]:,.2f} 差额{diff:,.2f}"
        for voucher, diff in mismatches[:5]
    )
    message = (
        f"序时账逐凭证借贷平衡: 校验通过（共 {len(debit.keys() | credit.keys())} 张凭证）"
        if passed
        else f"序时账逐凭证借贷平衡: 发现 {len(mismatches)} 张凭证不平衡。{detail}"
    )
    return [
        ValidationResult(
            rule_id="JNL-BAL-001",
            rule_name="序时账逐凭证借贷平衡",
            passed=passed,
            severity=Severity.ERROR,
            left_value=math.fsum(debit.values()),
            right_value=math.fsum(credit.values()),
            diff=math.fsum(debit.values()) - math.fsum(credit.values()),
            tolerance=tolerance,
            formula="借方合计 == 贷方合计（按凭证）",
            message=message,
            category="L2-明细勾稽",
        )
    ]


def check_cash_flow_detail_vs_statement(
    dataset: DetailDataset,
    reports: dict[ReportType, Report],
    tolerance: float,
) -> list[ValidationResult]:
    """核对现金流量明细各项目合计与现金流量表主表。"""
    report = reports.get(ReportType.CASH_FLOW_STATEMENT)
    if report is None:
        return [_missing_report_result("CF-DTL-001", "现金流量明细=现金流量表", "现金流量表")]

    statement = {clean_name(item.name): item.amount for item in report.items}
    inflow: dict[str, float] = defaultdict(float)
    outflow: dict[str, float] = defaultdict(float)
    for row in dataset.cash_flow_detail:
        if row.summary == "小计":
            continue
        key = clean_name(row.project)
        if row.direction == "流入":
            inflow[key] += row.amount
        elif row.direction == "流出":
            outflow[key] += row.amount

    results: list[ValidationResult] = []
    for key in inflow.keys() | outflow.keys():
        alias = CF_PROJECT_ALIASES.get(key, key)
        amount = inflow[key] if inflow[key] > 0 else outflow[key]
        statement_amount = statement.get(alias)
        if statement_amount is None:
            # P1: 明细项目在主表无对应行通常是科目映射缺口, 降级为跳过+提示,
            # 不作为异常/不通过 (宁可漏报不可误报)
            results.append(
                ValidationResult(
                    rule_id="CF-DTL-001",
                    rule_name="现金流量明细=现金流量表",
                    passed=True,
                    severity=Severity.WARNING,
                    left_value=amount,
                    right_value=0.0,
                    diff=amount,
                    tolerance=tolerance,
                    formula="明细项目合计 == 主表项目",
                    message=f"现金流量明细项目「{key}」未在主表中找到对应项目, 已跳过核对该项",
                    skipped=True,
                    category="L2-明细勾稽",
                )
            )
            continue
        diff = amount - statement_amount
        passed = abs(diff) <= tolerance
        results.append(
            ValidationResult(
                rule_id="CF-DTL-001",
                rule_name="现金流量明细=现金流量表",
                passed=passed,
                severity=Severity.ERROR,
                left_value=amount,
                right_value=statement_amount,
                diff=diff,
                tolerance=tolerance,
                formula="明细项目合计 == 主表项目",
                message=(
                    f"现金流量明细「{key}」合计 {amount:,.2f} == 主表 "
                    f"{statement_amount:,.2f}: {'一致' if passed else f'差额 {diff:,.2f}'}"
                ),
                category="L2-明细勾稽",
            )
        )
    return results


def check_cash_flow_detail_vs_journal(
    dataset: DetailDataset,
    cash_equivalent_codes: tuple[str, ...],
    tolerance: float,
) -> list[ValidationResult]:
    """按凭证核对现金流明细金额与序时账现金科目净变动。"""
    detail_net: dict[str, float] = defaultdict(float)
    for row in dataset.cash_flow_detail:
        if row.summary == "小计" or not row.voucher_no:
            continue
        sign = 1.0 if row.direction == "流入" else -1.0
        detail_net[row.voucher_no] += sign * row.amount

    journal_net: dict[str, float] = defaultdict(float)
    for journal_row in dataset.journal:
        if not any(
            journal_row.account_code.startswith(code) for code in cash_equivalent_codes
        ):
            continue
        sign = 1.0 if journal_row.direction == "借" else -1.0
        journal_net[journal_row.voucher_no] += sign * journal_row.amount

    mismatches = [
        (voucher, detail_net[voucher] - journal_net[voucher])
        for voucher in detail_net.keys() & journal_net.keys()
        if abs(detail_net[voucher] - journal_net[voucher]) > tolerance
    ]
    passed = not mismatches
    detail = "；".join(
        f"凭证{voucher} 明细{detail_net[voucher]:,.2f}/序时账{journal_net[voucher]:,.2f}"
        for voucher, _diff in mismatches[:5]
    )
    message = (
        "现金流明细与序时账现金科目核对: 校验通过"
        if passed
        else f"现金流明细与序时账核对: {len(mismatches)} 个凭证不一致。{detail}"
    )
    return [
        ValidationResult(
            rule_id="CF-JNL-001",
            rule_name="现金流明细=序时账现金科目",
            passed=passed,
            severity=Severity.WARNING,
            left_value=math.fsum(detail_net.values()),
            right_value=math.fsum(journal_net.values()),
            diff=math.fsum(detail_net.values()) - math.fsum(journal_net.values()),
            tolerance=tolerance,
            formula="明细金额 == 现金等价物科目净变动（按凭证）",
            message=message,
            category="L2-明细勾稽",
        )
    ]


def check_trial_balance_vs_balance_sheet(
    dataset: DetailDataset,
    reports: dict[ReportType, Report],
    mappings: dict[str, dict[str, object]],
    tolerance: float,
) -> list[ValidationResult]:
    """按科目映射核对余额表期末余额与资产负债表项目。"""
    report = reports.get(ReportType.BALANCE_SHEET)
    if report is None:
        return [_missing_report_result("TB-BS-001", "余额表=资产负债表", "资产负债表")]

    amounts = {item.key: item.amount for item in report.items}
    results: list[ValidationResult] = []
    for item_key, config in mappings.items():
        codes_raw = config["codes"]
        codes = (
            (codes_raw,) if isinstance(codes_raw, str) else cast(tuple[str, ...], codes_raw)
        )
        side = str(config.get("side", "debit"))
        expected = _sum_trial_balance(dataset, codes, side)
        actual = amounts.get(item_key)
        if actual is None:
            continue
        diff = expected - actual
        passed = abs(diff) <= tolerance
        results.append(
            ValidationResult(
                rule_id="TB-BS-001",
                rule_name="余额表=资产负债表",
                passed=passed,
                severity=Severity.ERROR,
                left_value=expected,
                right_value=actual,
                diff=diff,
                tolerance=tolerance,
                formula="余额表期末余额 == 报表项目",
                message=(
                    f"余额表科目 {codes} 合计 {expected:,.2f} vs 报表「{item_key}」"
                    f"{actual:,.2f}: {'一致' if passed else f'差额 {diff:,.2f}'}"
                ),
                category="L2-明细勾稽",
            )
        )
    return results


def _sum_trial_balance(
    dataset: DetailDataset, codes: tuple[str, ...], side: str
) -> float:
    """汇总余额表指定科目期末余额（前缀匹配 + 父级排除）。

    匹配规则：科目编码以任一映射编码开头即纳入，与序时账侧
    check_cash_flow_detail_vs_journal 的 startswith 口径（:160-161）一致。
    再排除「其编码是另一匹配行编码的真前缀」的父级行——余额表若一级
    科目与末级科目混列，一级行金额已含末级明细，不排除会重复加总。
    """
    matched = [
        row
        for row in dataset.trial_balance
        if any(row.account_code.startswith(c) for c in codes)
    ]
    matched_codes = [row.account_code for row in matched]
    total = 0.0
    for row in matched:
        # 父级排除：存在另一匹配行的编码以本行编码为真前缀时，本行为父级，跳过
        if any(
            other != row.account_code and other.startswith(row.account_code)
            for other in matched_codes
        ):
            continue
        if side == "credit":
            total += row.ending_credit - row.ending_debit
        else:
            total += row.ending_debit - row.ending_credit
    return total


def _missing_report_result(
    rule_id: str, rule_name: str, report_name: str
) -> ValidationResult:
    """缺少所需主表时的跳过结果。"""
    return ValidationResult(
        rule_id=rule_id,
        rule_name=rule_name,
        passed=True,
        severity=Severity.INFO,
        left_value=0.0,
        right_value=0.0,
        diff=0.0,
        tolerance=0.0,
        formula="",
        message=f"{rule_name}: 跳过 - 缺少{report_name}",
        skipped=True,
        category="L2-明细勾稽",
    )

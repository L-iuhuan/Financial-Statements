"""L4 现金流选择正确性检查（凭证级，保守提示）。"""

from __future__ import annotations

from collections import defaultdict

from fsa.core.engine.cash_flow_rules import (
    DEFAULT_CASH_FLOW_RULES,
    CashFlowClassificationRule,
)
from fsa.core.models.detail import DetailDataset
from fsa.core.models.result import ValidationResult
from fsa.core.models.rule import Severity


def check_cash_flow_classification(
    dataset: DetailDataset,
    cash_equivalent_codes: tuple[str, ...],
    tolerance: float,
) -> list[ValidationResult]:
    """按现金流分类规则复核凭证的现金流项目选择。"""
    counterparts = _voucher_counterparts(dataset, cash_equivalent_codes)
    results: list[ValidationResult] = []
    for rule in DEFAULT_CASH_FLOW_RULES:
        suspicious, voucher_count = _suspicious_vouchers(dataset, rule, counterparts)
        passed = not suspicious
        detail = "；".join(
            f"凭证{voucher} 对方科目 {accounts}"
            for voucher, accounts in suspicious[:5]
        )
        if voucher_count == 0:
            message = f"现金流分类「{rule.project_keyword}」: 本期无对应凭证"
        elif passed:
            message = f"现金流分类「{rule.project_keyword}」: 复核通过"
        else:
            message = (
                f"现金流分类「{rule.project_keyword}」: {len(suspicious)} 张凭证"
                f"对方科目不在常见范围，请复核。{detail}"
            )
        results.append(
            ValidationResult(
                rule_id=rule.rule_id,
                rule_name=f"现金流选择: {rule.project_keyword}",
                passed=passed,
                severity=Severity.WARNING,
                left_value=float(len(suspicious)),
                right_value=0.0,
                diff=float(len(suspicious)),
                tolerance=tolerance,
                formula="现金流量项目 ↔ 序时账对方科目",
                message=message,
                category="L4-现金流选择",
            )
        )
    return results


def check_cash_flow_coverage(
    dataset: DetailDataset,
    cash_equivalent_codes: tuple[str, ...],
    tolerance: float,
) -> ValidationResult:
    """检查有现金变动的凭证是否都指定了现金流量项目。"""
    cash_vouchers = {
        row.voucher_no
        for row in dataset.journal
        if any(row.account_code.startswith(code) for code in cash_equivalent_codes)
    }
    detail_vouchers = {
        row.voucher_no
        for row in dataset.cash_flow_detail
        if row.summary != "小计" and row.voucher_no
    }
    missing = sorted(cash_vouchers - detail_vouchers)
    passed = not missing
    message = (
        "现金流明细覆盖率: 所有现金凭证均已指定现金流项目"
        if passed
        else f"现金流明细覆盖率: {len(missing)} 张现金凭证未指定现金流项目。"
        + "；".join(missing[:10])
    )
    return ValidationResult(
        rule_id="CF-CLS-901",
        rule_name="现金流明细覆盖率",
        passed=passed,
        severity=Severity.WARNING,
        left_value=float(len(detail_vouchers)),
        right_value=float(len(cash_vouchers)),
        diff=float(len(cash_vouchers) - len(detail_vouchers)),
        tolerance=tolerance,
        formula="现金凭证集合 ⊆ 现金流明细凭证集合",
        message=message,
        category="L4-现金流选择",
    )


def _voucher_counterparts(
    dataset: DetailDataset,
    cash_equivalent_codes: tuple[str, ...],
) -> dict[str, set[str]]:
    """返回 凭证号 -> 非现金对方科目（前 4 位）集合。"""
    result: dict[str, set[str]] = defaultdict(set)
    for row in dataset.journal:
        if any(row.account_code.startswith(code) for code in cash_equivalent_codes):
            continue
        result[row.voucher_no].add(row.account_code[:4])
    return dict(result)


def _suspicious_vouchers(
    dataset: DetailDataset,
    rule: CashFlowClassificationRule,
    counterparts: dict[str, set[str]],
) -> tuple[list[tuple[str, str]], int]:
    """找出对方科目不在规则常见范围内的凭证。"""
    vouchers = {
        row.voucher_no
        for row in dataset.cash_flow_detail
        if row.summary != "小计"
        and row.direction == rule.direction
        and rule.project_keyword in _strip_suo(row.project)
    }
    suspicious: list[tuple[str, str]] = []
    for voucher in sorted(vouchers):
        accounts = counterparts.get(voucher, set())
        if not accounts:
            continue
        matched = any(
            account.startswith(prefix)
            for account in accounts
            for prefix in rule.counterpart_prefixes
        )
        if not matched:
            suspicious.append((voucher, "/".join(sorted(accounts)[:5])))
    return suspicious, len(vouchers)


def _strip_suo(project_name: str) -> str:
    """去除现金流量项目名中的「所」字，容忍企业导出用词差异。

    例如「投资所支付的现金」→「投资支付的现金」，
    使规则关键字「投资支付的现金」可以命中。
    """
    return project_name.replace("所", "")

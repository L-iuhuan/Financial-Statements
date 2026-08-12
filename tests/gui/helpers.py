"""GUI 测试辅助函数。"""

from __future__ import annotations

from fsa.core.engine.registry import RuleRegistry
from fsa.core.models.report import Report, ReportItem, ReportType
from fsa.core.models.result import TraceItem, ValidationResult, ValidationSummary
from fsa.core.models.rule import ReconciliationRule, Severity, ToleranceType


def make_rule(
    rule_id: str = "X-001",
    name: str = "测试规则",
    category: str = "A-表内平衡",
    statements: list[str] | None = None,
    severity: Severity = Severity.ERROR,
    tolerance: float = 0.01,
    formula: str = "a == b",
) -> ReconciliationRule:
    """创建一条测试规则。"""
    return ReconciliationRule(
        rule_id=rule_id,
        name=name,
        category=category,
        statements=statements or ["资产负债表"],
        formula=formula,
        tolerance_type=ToleranceType.EXACT,
        tolerance=tolerance,
        severity=severity,
    )


def make_result(
    rule_id: str = "X-001",
    rule_name: str = "测试规则",
    passed: bool = True,
    severity: Severity = Severity.ERROR,
    diff: float = 0.0,
    errored: bool = False,
    category: str = "A-表内平衡",
    trace: list[TraceItem] | None = None,
) -> ValidationResult:
    """创建一个校验结果。"""
    return ValidationResult(
        rule_id=rule_id,
        rule_name=rule_name,
        passed=passed,
        severity=severity,
        left_value=100.0,
        right_value=100.0 - diff,
        diff=diff,
        tolerance=0.01,
        formula="a == b",
        message="",
        errored=errored,
        category=category,
        trace=trace or [],
    )


def make_summary(results: list[ValidationResult]) -> ValidationSummary:
    """创建校验汇总。"""
    passed = sum(1 for r in results if r.passed and not r.errored)
    failed = sum(1 for r in results if not r.passed and not r.errored)
    errored = sum(1 for r in results if r.errored)
    return ValidationSummary(
        total=len(results),
        passed=passed,
        failed=failed,
        errored=errored,
        results=results,
    )


def make_registry() -> RuleRegistry:
    """创建包含三条规则的注册表。"""
    rules = [
        make_rule("A-001", category="A-表内平衡", severity=Severity.ERROR),
        make_rule(
            "B-001",
            category="B-表间勾稽",
            statements=["资产负债表", "利润表"],
            severity=Severity.WARNING,
        ),
        make_rule(
            "C-001",
            category="C-逻辑合理性",
            statements=["现金流量表"],
            severity=Severity.INFO,
        ),
    ]
    return RuleRegistry(rules)


def make_report() -> Report:
    """创建一张测试报表。"""
    return Report(
        report_type=ReportType.BALANCE_SHEET,
        period="2024-12",
        source_file="test.xlsx",
        items=[
            ReportItem(key="asset_total", name="资产总计", amount=100.0, row=35),
            ReportItem(key="liability_total", name="负债合计", amount=60.0, row=20),
            ReportItem(key="equity_total", name="所有者权益合计", amount=40.0, row=30),
        ],
    )

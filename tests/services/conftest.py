"""服务层测试 fixtures: 工厂函数创建规则、注册表、多表报表。"""

from __future__ import annotations

from fsa.core.engine.registry import RuleRegistry
from fsa.core.models.report import Report, ReportItem, ReportType
from fsa.core.models.rule import ReconciliationRule, Severity, ToleranceType


def make_rule(
    rule_id: str = "BS-BAL-001",
    name: str = "资产=负债+所有者权益",
    category: str = "A-表内平衡",
    statements: list[str] | None = None,
    formula: str = "asset_total == liability_total + equity_total",
    tolerance_type: ToleranceType = ToleranceType.EXACT,
    tolerance: float = 0.01,
    severity: Severity = Severity.ERROR,
) -> ReconciliationRule:
    """创建自定义规则。"""
    if statements is None:
        statements = ["资产负债表"]
    return ReconciliationRule(
        rule_id=rule_id,
        name=name,
        category=category,
        statements=statements,
        formula=formula,
        tolerance_type=tolerance_type,
        tolerance=tolerance,
        severity=severity,
    )


def make_registry(rules: list[ReconciliationRule]) -> RuleRegistry:
    """从规则列表创建注册表。"""
    return RuleRegistry(rules)


def make_item(
    key: str,
    name: str,
    amount: float = 0.0,
    row: int = 1,
    column: str = "期末余额",
) -> ReportItem:
    """创建一个 ReportItem。"""
    return ReportItem(key=key, name=name, amount=amount, row=row, column=column)


def make_income_statement(
    revenue: float = 0.0,
    expenses: float = 0.0,
    net_profit: float = 0.0,
    period: str = "2024-12",
) -> Report:
    """创建利润表。"""
    return Report(
        report_type=ReportType.INCOME_STATEMENT,
        period=period,
        items=[
            make_item("revenue", "营业收入", revenue, row=1),
            make_item("expenses", "营业成本及费用", expenses, row=10),
            make_item("net_profit", "净利润", net_profit, row=20),
        ],
    )


def make_cash_flow_statement(
    operating_cf: float = 0.0,
    investing_cf: float = 0.0,
    financing_cf: float = 0.0,
    net_cf: float = 0.0,
    period: str = "2024-12",
) -> Report:
    """创建现金流量表。"""
    return Report(
        report_type=ReportType.CASH_FLOW_STATEMENT,
        period=period,
        items=[
            make_item("operating_cf", "经营活动现金流量净额", operating_cf, row=5),
            make_item("investing_cf", "投资活动现金流量净额", investing_cf, row=10),
            make_item("financing_cf", "筹资活动现金流量净额", financing_cf, row=15),
            make_item("net_cf", "现金及现金等价物净增加额", net_cf, row=20),
        ],
    )

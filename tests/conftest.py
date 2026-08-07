"""共享测试 fixtures: 工厂函数创建测试数据。

每个工厂函数返回标准测试对象，减少测试中的样板代码。
"""

from __future__ import annotations

from fsa.core.models.report import Report, ReportItem, ReportType
from fsa.core.models.rule import ReconciliationRule, Severity, ToleranceType
from fsa.core.models.result import ValidationContext


def make_item(
    key: str = "asset_total",
    name: str = "资产总计",
    amount: float = 0.0,
    row: int = 1,
    column: str = "期末余额",
) -> ReportItem:
    """创建一个 ReportItem。"""
    return ReportItem(key=key, name=name, amount=amount, row=row, column=column)


def make_balance_sheet(
    asset_total: float = 0.0,
    liability_total: float = 0.0,
    equity_total: float = 0.0,
    current_assets: float | None = None,
    non_current_assets: float | None = None,
    current_liabilities: float | None = None,
    non_current_liabilities: float | None = None,
    period: str = "2024-12",
) -> Report:
    """创建资产负债表，包含 BS-BAL-001 到 BS-BAL-004 所需的标准项目。"""
    items = [
        make_item("asset_total", "资产总计", asset_total, row=35),
        make_item("liability_total", "负债合计", liability_total, row=20),
        make_item("equity_total", "所有者权益合计", equity_total, row=30),
    ]
    if current_assets is not None:
        items.append(make_item("current_assets", "流动资产合计", current_assets, row=10))
    if non_current_assets is not None:
        items.append(
            make_item("non_current_assets", "非流动资产合计", non_current_assets, row=25)
        )
    if current_liabilities is not None:
        items.append(
            make_item("current_liabilities", "流动负债合计", current_liabilities, row=15)
        )
    if non_current_liabilities is not None:
        items.append(
            make_item(
                "non_current_liabilities", "非流动负债合计", non_current_liabilities, row=18
            )
        )
    return Report(
        report_type=ReportType.BALANCE_SHEET,
        period=period,
        items=items,
    )


def make_rule_bs_bal_001() -> ReconciliationRule:
    """创建 BS-BAL-001 规则: 资产=负债+所有者权益。"""
    return ReconciliationRule(
        rule_id="BS-BAL-001",
        name="资产=负债+所有者权益",
        category="A-表内平衡",
        statements=["资产负债表"],
        formula="asset_total == liability_total + equity_total",
        tolerance_type=ToleranceType.EXACT,
        tolerance=0.01,
        severity=Severity.ERROR,
        cas_ref="《企业会计准则--基本准则》第5条/第43条; 会计恒等式",
        notes="基本平衡关系; 破坏即报表编制错误",
    )


def make_context(
    asset_total: float = 100.0,
    liability_total: float = 60.0,
    equity_total: float = 40.0,
) -> ValidationContext:
    """创建包含标准资产负债表的校验上下文。"""
    bs = make_balance_sheet(
        asset_total=asset_total,
        liability_total=liability_total,
        equity_total=equity_total,
    )
    ctx = ValidationContext(period="2024-12")
    ctx.add_report(bs)
    return ctx

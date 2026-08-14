"""共享测试 fixtures: 工厂函数创建测试数据。

每个工厂函数返回标准测试对象，减少测试中的样板代码。
"""

from __future__ import annotations

from fsa.core.models.report import Report, ReportItem, ReportType
from fsa.core.models.result import ValidationContext
from fsa.core.models.rule import ReconciliationRule, Severity, ToleranceType


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


def make_income_statement(
    revenue: float = 0.0,
    operating_cost: float = 0.0,
    net_profit: float = 0.0,
    operating_profit: float | None = None,
    total_profit: float | None = None,
    taxes_surcharges: float | None = None,
    selling_exp: float | None = None,
    admin_exp: float | None = None,
    rnd_exp: float | None = None,
    finance_exp: float | None = None,
    period: str = "2024-12",
) -> Report:
    """创建利润表，包含利润表校验所需的标准项目。"""
    items = [
        make_item("revenue", "营业收入", revenue, row=1),
        make_item("operating_cost", "营业成本", operating_cost, row=4),
        make_item("net_profit", "净利润", net_profit, row=30),
    ]
    if operating_profit is not None:
        items.append(make_item("operating_profit", "营业利润", operating_profit, row=20))
    if total_profit is not None:
        items.append(make_item("total_profit", "利润总额", total_profit, row=25))
    if taxes_surcharges is not None:
        items.append(make_item("taxes_surcharges", "税金及附加", taxes_surcharges, row=5))
    if selling_exp is not None:
        items.append(make_item("selling_exp", "销售费用", selling_exp, row=6))
    if admin_exp is not None:
        items.append(make_item("admin_exp", "管理费用", admin_exp, row=7))
    if rnd_exp is not None:
        items.append(make_item("rnd_exp", "研发费用", rnd_exp, row=8))
    if finance_exp is not None:
        items.append(make_item("finance_exp", "财务费用", finance_exp, row=9))
    return Report(
        report_type=ReportType.INCOME_STATEMENT,
        period=period,
        items=items,
    )


def make_cash_flow_statement(
    operating_net: float = 0.0,
    investing_net: float = 0.0,
    financing_net: float = 0.0,
    net_increase_cash: float = 0.0,
    ending_cash_equiv: float | None = None,
    beginning_cash_equiv: float | None = None,
    period: str = "2024-12",
) -> Report:
    """创建现金流量表，包含现金流量表校验所需的标准项目。"""
    items = [
        make_item("operating_net", "经营活动产生的现金流量净额", operating_net, row=5),
        make_item("investing_net", "投资活动产生的现金流量净额", investing_net, row=10),
        make_item("financing_net", "筹资活动产生的现金流量净额", financing_net, row=15),
        make_item("net_increase_cash", "现金及现金等价物净增加额", net_increase_cash, row=20),
    ]
    if ending_cash_equiv is not None:
        items.append(make_item("ending_cash_equiv", "期末现金及现金等价物余额", ending_cash_equiv, row=25))
    if beginning_cash_equiv is not None:
        items.append(make_item("beginning_cash_equiv", "期初现金及现金等价物余额", beginning_cash_equiv, row=24))
    return Report(
        report_type=ReportType.CASH_FLOW_STATEMENT,
        period=period,
        items=items,
    )


def make_sce_report(
    paid_in_capital: float = 0.0,
    capital_reserve: float = 0.0,
    other_comprehensive: float = 0.0,
    surplus_reserve: float = 0.0,
    undistributed_profit: float = 0.0,
    equity_total: float = 0.0,
    period: str = "2024-12",
) -> Report:
    """创建所有者权益变动表（SCE），项目使用 sce_ 前缀 key（期末口径）。"""
    items = [
        make_item("sce_paid_in_capital_ending", "实收资本(本年年末余额)", paid_in_capital, row=5, column="实收资本"),
        make_item("sce_capital_reserve_ending", "资本公积(本年年末余额)", capital_reserve, row=6, column="资本公积"),
        make_item("sce_other_comprehensive_ending", "其他综合收益(本年年末余额)", other_comprehensive, row=7, column="其他综合收益"),
        make_item("sce_surplus_reserve_ending", "盈余公积(本年年末余额)", surplus_reserve, row=8, column="盈余公积"),
        make_item("sce_undistributed_profit_ending", "未分配利润(本年年末余额)", undistributed_profit, row=9, column="未分配利润"),
        make_item("sce_equity_total_ending", "所有者权益合计(本年年末余额)", equity_total, row=10, column="所有者权益合计"),
    ]
    return Report(
        report_type=ReportType.STATEMENT_OF_CHANGES_IN_EQUITY,
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

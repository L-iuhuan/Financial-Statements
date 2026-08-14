"""校验结果数据模型: ValidationResult, ValidationContext。

ValidationContext 是一次校验运行的上下文，包含所有报表。
ValidationResult 是一条规则的校验结果。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fsa.core.models.report import Report, ReportItem, ReportType
from fsa.core.models.rule import ReconciliationRule, Severity

# CAS 三大报表的标准科目 key 集合。
# 这些科目在报表中缺失时默认为 0（企业没有该项目 = 金额为 0）。
# 注意: 附注/间接法调节变量（depreciation, amortization 等）不在此集合中，
# 缺少这些变量的规则将被跳过而非以 0 求值。
KNOWN_LINE_ITEM_KEYS: frozenset[str] = frozenset({
    # BS - 流动资产
    "monetary_funds", "trading_financial_assets", "notes_receivable",
    "accounts_receivable", "prepayments", "other_receivable",
    "inventory", "contract_assets", "held_for_sale_assets", "current_assets",
    # BS - 非流动资产
    "fixed_assets", "construction_in_progress", "intangible_assets",
    "goodwill", "long_term_prepaid_expenses", "deferred_tax_assets",
    "non_current_assets", "asset_total",
    # BS - 流动负债
    "short_term_borrowings", "notes_payable", "accounts_payable",
    "advance_from_customers", "employee_benefits_payable",
    "taxes_payable", "other_payable", "current_portion_non_current_liab",
    "current_liabilities",
    # BS - 非流动负债
    "long_term_borrowings", "bonds_payable", "lease_liabilities",
    "deferred_tax_liabilities", "non_current_liabilities", "liability_total",
    # BS - 所有者权益
    "paid_in_capital", "capital_reserve", "treasury_stock",
    "other_comprehensive_income", "surplus_reserve", "undistributed_profit",
    "equity_total", "liability_equity_total", "minority_interest",
    "parent_equity", "general_risk_reserve", "special_reserve",
    "other_equity_instruments",
    # IS
    "revenue", "operating_cost",
    # NOTE: total_revenue/total_operating_cost intentionally excluded.
    # 仅 IS-BAL-001 使用 (营业总收入/总成本格式)。若预填 0, 标准分项格式报表
    # (营业收入/营业成本) 会误报不通过。移出后此类报表 IS-BAL-001 跳过 (P1).
    # 部分企业报表实际包含这两项, 仍会被提取入 namespace, 校验不受影响。
    "interest_income", "interest_expense", "fee_commission_income",
    "fee_commission_expense", "earned_premium", "surrender_value",
    "claim_payment", "insurance_reserve_change", "policy_dividend_expense",
    "reinsurance_cost", "taxes_surcharges", "selling_exp", "admin_exp",
    "rnd_exp", "finance_exp", "other_income", "investment_income",
    "fair_value_change", "credit_impairment", "asset_impairment",
    "asset_disposal_gain", "operating_profit", "non_operating_income",
    "non_operating_expense", "total_profit", "income_tax_expense",
    "net_profit",
    # NOTE: primary_revenue/other_revenue intentionally excluded -
    # they're optional sub-items not present in all reports.
    # When missing, IS-BAL-004 formula raises EvaluationError -> skip (P1).
    "total_comprehensive_income", "other_comprehensive_income_after_tax",
    "non_recurring_net_profit",
    # CF
    "cash_received_from_sales", "tax_refunds_received",
    "other_operating_cash_inflow", "operating_cash_inflow",
    "cash_paid_for_purchases", "cash_paid_for_employees", "taxes_paid",
    "other_operating_cash_outflow", "operating_cash_outflow",
    "operating_net", "cash_from_investment_recovery",
    "cash_from_investment_income", "cash_from_asset_disposal",
    "investing_cash_inflow", "cash_paid_for_fixed_assets",
    "cash_paid_for_investments", "investing_cash_outflow", "investing_net",
    "cash_from_borrowings", "financing_cash_inflow", "cash_for_debt_repayment",
    "cash_for_dividends", "financing_cash_outflow", "financing_net",
    "net_increase_cash", "fx_effect", "beginning_cash_equiv",
    "ending_cash_equiv",
    # NOTE: dividends/surplus_withheld/prior_period_adjust/restricted_adjust
    # intentionally EXCLUDED — they have no data source in the three main
    # statements. If pre-filled with 0, BS-IS-001 would falsely fail for
    # companies with real dividend distributions.
    # Per P1 (宁可漏报不可误报), rules using them skip instead.
})


@dataclass
class TraceItem:
    """校验追踪项：记录公式中一个变量的来源信息。

    Attributes:
        key: 变量名，如 "asset_total"
        name: 中文科目名，如 "资产总计"
        amount: 金额（元）
        row: 在源文件中的行号
        column: 在源文件中的列名
        side: 公式侧，"left" 或 "right"
    """

    key: str
    name: str
    amount: float
    row: int
    column: str
    side: str


@dataclass
class ValidationResult:
    """一条规则的校验结果。

    Attributes:
        rule_id: 规则编号
        rule_name: 规则名称
        passed: 是否通过
        severity: 严重级别
        left_value: 公式左侧计算值
        right_value: 公式右侧计算值
        diff: 差额 = left_value - right_value
        tolerance: 使用的容差
        formula: 公式原文（用于显示）
        message: 面向财务用户的中文消息
        errored: 是否因异常而未能完成校验（缺失科目、公式错误等）
        category: 规则分类，如 "A-表内平衡"
        trace: 校验追踪列表，记录公式中每个变量的来源
    """

    rule_id: str
    rule_name: str
    passed: bool
    severity: Severity
    left_value: float
    right_value: float
    diff: float
    tolerance: float
    formula: str
    message: str
    errored: bool = False
    skipped: bool = False
    category: str = ""
    trace: list[TraceItem] = field(default_factory=list)

    @classmethod
    def from_error(
        cls, rule: ReconciliationRule, error_message: str
    ) -> ValidationResult:
        """从异常创建校验结果（规则未能完成执行）。"""
        return cls(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            passed=False,
            severity=rule.severity,
            left_value=0.0,
            right_value=0.0,
            diff=0.0,
            tolerance=rule.tolerance,
            formula=rule.formula,
            message=f"{rule.name}: 无法执行校验 - {error_message}",
            errored=True,
            category=rule.category,
        )

    @classmethod
    def from_skip(
        cls, rule: ReconciliationRule, skip_reason: str
    ) -> ValidationResult:
        """创建跳过结果（规则因缺少数据无法执行，不算不通过）。"""
        return cls(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            passed=True,
            severity=rule.severity,
            left_value=0.0,
            right_value=0.0,
            diff=0.0,
            tolerance=rule.tolerance,
            formula=rule.formula,
            message=f"{rule.name}: 跳过 - {skip_reason}",
            skipped=True,
            category=rule.category,
        )


@dataclass
class ValidationSummary:
    """一次校验运行的汇总结果。

    Attributes:
        period: 报告期间
        total: 实际执行的规则数
        passed: 通过数
        failed: 不通过数（差额超容差）
        errored: 异常数（缺失科目、公式错误等）
        skipped: 跳过数（所需报表未导入）
        results: 所有校验结果明细
        report_types: 本次校验涉及的报表类型
    """

    period: str = ""
    total: int = 0
    passed: int = 0
    failed: int = 0
    errored: int = 0
    skipped: int = 0
    results: list[ValidationResult] = field(default_factory=list)
    report_types: list[ReportType] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        """是否全部通过（无不通过、无异常）。"""
        return self.failed == 0 and self.errored == 0

    @property
    def success_rate(self) -> float:
        """通过率（异常不计入分母）。无规则执行时返回 1.0。"""
        if self.total == 0:
            return 1.0
        return self.passed / self.total

    @property
    def failed_results(self) -> list[ValidationResult]:
        """仅不通过的结果（含异常）。"""
        return [r for r in self.results if not r.passed]


@dataclass
class ValidationContext:
    """一次校验运行的上下文。

    包含所有待校验的报表，按 ReportType 索引。
    规则引擎从此上下文中获取报表数据，构建变量命名空间。

    Attributes:
        reports: 报表字典，按 ReportType 索引
        period: 报告期间
    """

    reports: dict[ReportType, Report] = field(default_factory=dict)
    period: str = ""

    def add_report(self, report: Report) -> None:
        """添加一张报表。已存在同类型则覆盖。"""
        self.reports[report.report_type] = report

    def get_report(self, report_type: ReportType) -> Report | None:
        """获取指定类型的报表。不存在返回 None。"""
        return self.reports.get(report_type)

    def get_item(self, key: str) -> ReportItem | None:
        """在所有报表中搜索指定 key 的项目。

        搜索顺序: 遍历所有报表，包括 cf_notes_ 前缀的 key。

        Args:
            key: 变量名，如 "asset_total" 或 "cf_notes_net_profit"

        Returns:
            ReportItem，未找到返回 None
        """
        for report in self.reports.values():
            item = report.get_item(key)
            if item is not None:
                return item
        return None

    def build_namespace(self, statement_names: list[str]) -> dict[str, float]:
        """根据规则涉及的报表类型，构建变量命名空间。

        将相关报表中的所有 ReportItem 的 key->amount 映射合并到一个字典中。
        预填充已知 CAS 科目为 0.0（企业没有该项目 = 金额为 0），再用实际数据覆盖。
        为每个 item 同时设置 {key}_ending 和 {key}_beginning 变量（如果 beginning_amount 不为 None）。
        如果同一个 key 在多张报表中出现，抛出 ValueError。

        Args:
            statement_names: 规则涉及的报表中文名列表，如 ["资产负债表"]

        Returns:
            变量命名空间，如 {"asset_total": 1000000.0, "asset_total_ending": 1000000.0}

        Raises:
            KeyError: 指定的报表类型不存在
            ValueError: 变量名冲突（同一 key 出现在多张报表中）
        """
        namespace: dict[str, float] = {key: 0.0 for key in KNOWN_LINE_ITEM_KEYS}
        seen_keys: set[str] = set()
        name_to_type = {rt.value: rt for rt in ReportType}

        for stmt_name in statement_names:
            report_type = name_to_type.get(stmt_name)
            if report_type is None:
                continue
            report = self.reports.get(report_type)
            if report is None:
                continue
            for item in report.items:
                if item.key in seen_keys:
                    raise ValueError(
                        f"变量「{item.key}」在多张报表中重复定义"
                    )
                seen_keys.add(item.key)
                namespace[item.key] = item.amount
                # 设置 {key}_ending 变量
                namespace[f"{item.key}_ending"] = item.amount
                # 设置 {key}_beginning 变量（仅当 beginning_amount 不为 None）
                if item.beginning_amount is not None:
                    namespace[f"{item.key}_beginning"] = item.beginning_amount
        return namespace

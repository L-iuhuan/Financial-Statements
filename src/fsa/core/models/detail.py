"""明细数据模型: 科目余额表、序时账、现金流量明细。

与 Report（汇总报表）解耦。DetailDataset 是一次导入的完整明细数据集，
供明细层勾稽检查（L2~L4）使用。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TrialBalanceRow:
    """科目余额表的一行。

    Attributes:
        account_code: 科目编码，如 "1002"、"100201"
        account_name: 科目名称
        scope: 期间口径，"本月" 或 "1-本月"
        beginning_debit: 期初余额借方
        beginning_credit: 期初余额贷方
        period_debit: 本期发生借方
        period_credit: 本期发生贷方
        ending_debit: 期末余额借方
        ending_credit: 期末余额贷方
        row: 源文件行号
    """

    account_code: str
    account_name: str
    scope: str = ""
    beginning_debit: float = 0.0
    beginning_credit: float = 0.0
    period_debit: float = 0.0
    period_credit: float = 0.0
    ending_debit: float = 0.0
    ending_credit: float = 0.0
    row: int = 0


@dataclass(frozen=True)
class JournalRow:
    """序时账的一行分录。

    Attributes:
        date: 记账日期字符串
        voucher_no: 凭证号，如 "记-0001"
        parent_account: 上级科目路径，如 "管理费用/水电费/电费"
        account_code: 科目编码
        account_name: 科目名称
        summary: 摘要
        direction: 方向，"借" 或 "贷"
        amount: 金额（元）
        row: 源文件行号
    """

    date: str
    voucher_no: str
    parent_account: str
    account_code: str
    account_name: str
    summary: str
    direction: str
    amount: float
    row: int = 0


@dataclass(frozen=True)
class CashFlowDetailRow:
    """现金流量明细的一行。

    Attributes:
        voucher_no: 凭证号
        project: 现金流量项目，如 "销售商品、提供劳务收到的现金(01)"
        summary: 摘要（"小计" 表示汇总行）
        direction: 方向，"流入" 或 "流出"
        amount: 金额（元）
        month: 月份（1~12），缺失为 0
        day: 日，缺失为 0
        row: 源文件行号
    """

    voucher_no: str
    project: str
    summary: str
    direction: str
    amount: float
    month: int = 0
    day: int = 0
    row: int = 0


@dataclass(frozen=True)
class ReclassificationRow:
    """往来重分类明细的一行（附表 3）。"""

    original_account: str
    counterparty: str
    book_amount: float
    reclassified_account: str
    reclassified_amount: float
    invoiced_amount: float = 0.0
    accrued_amount: float = 0.0
    is_related_party: str = ""
    note: str = ""
    row: int = 0


@dataclass(frozen=True)
class RelatedPartyPurchaseRow:
    """关联方采购明细的一行（附表 4）。"""

    buyer: str
    counterparty: str
    payment_nature: str
    total_amount: float
    supply_chain: float = 0.0
    mold: float = 0.0
    inventory: float = 0.0
    main_cost: float = 0.0
    other_cost: float = 0.0
    rnd_expense: float = 0.0
    admin_expense: float = 0.0
    selling_expense: float = 0.0
    other: float = 0.0
    difference_reason: str = ""
    row: int = 0


@dataclass(frozen=True)
class SalesDetailRow:
    """销售收入成本明细的一行（附表 5）。"""

    year: int
    month: int
    entity: str
    customer: str
    revenue_type: str
    revenue_amount: float
    cost_amount: float
    direct_material: float = 0.0
    processing: float = 0.0
    direct_labor: float = 0.0
    manufacturing: float = 0.0
    gross_margin: float | None = None
    row: int = 0


@dataclass(frozen=True)
class InternalCashFlowRow:
    """内部交易现金流明细的一行（附表 6）。"""

    month: int
    entity: str
    counterparty: str
    payment_nature: str
    project: str
    amount: float
    row: int = 0


@dataclass
class DetailDataset:
    """一次导入的完整明细数据集。"""

    entity: str = ""
    period: str = ""
    source_file: str = ""
    trial_balance: list[TrialBalanceRow] = field(default_factory=list)
    trial_balance_current: list[TrialBalanceRow] = field(default_factory=list)
    journal: list[JournalRow] = field(default_factory=list)
    journal_current: list[JournalRow] = field(default_factory=list)
    cash_flow_detail: list[CashFlowDetailRow] = field(default_factory=list)
    cash_flow_detail_current: list[CashFlowDetailRow] = field(default_factory=list)
    reclassifications: list[ReclassificationRow] = field(default_factory=list)
    related_party_purchases: list[RelatedPartyPurchaseRow] = field(default_factory=list)
    sales_details: list[SalesDetailRow] = field(default_factory=list)
    internal_cash_flows: list[InternalCashFlowRow] = field(default_factory=list)
    amount_unit: str = "元"
    unit_warnings: list[str] = field(default_factory=list)

    def merge(self, other: DetailDataset) -> None:
        """合并另一个数据集（多文件导入同一期间时使用）。"""
        if not self.period and other.period:
            self.period = other.period
        if not self.source_file:
            self.source_file = other.source_file
        if self.amount_unit == "元" and other.amount_unit != "元":
            self.amount_unit = other.amount_unit
        self.unit_warnings.extend(other.unit_warnings)
        self.trial_balance.extend(other.trial_balance)
        self.trial_balance_current.extend(other.trial_balance_current)
        self.journal.extend(other.journal)
        self.journal_current.extend(other.journal_current)
        self.cash_flow_detail.extend(other.cash_flow_detail)
        self.cash_flow_detail_current.extend(other.cash_flow_detail_current)
        self.reclassifications.extend(other.reclassifications)
        self.related_party_purchases.extend(other.related_party_purchases)
        self.sales_details.extend(other.sales_details)
        self.internal_cash_flows.extend(other.internal_cash_flows)

    @property
    def is_empty(self) -> bool:
        """明细数据是否全部为空（仅导入主表时跳过明细校验）。"""
        return not any(
            (
                self.trial_balance,
                self.trial_balance_current,
                self.journal,
                self.journal_current,
                self.cash_flow_detail,
                self.cash_flow_detail_current,
                self.reclassifications,
                self.related_party_purchases,
                self.sales_details,
                self.internal_cash_flows,
            )
        )

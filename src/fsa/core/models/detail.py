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


@dataclass
class DetailDataset:
    """一次导入的完整明细数据集。"""

    entity: str = ""
    period: str = ""
    source_file: str = ""
    trial_balance: list[TrialBalanceRow] = field(default_factory=list)
    trial_balance_current: list[TrialBalanceRow] = field(default_factory=list)
    journal: list[JournalRow] = field(default_factory=list)
    cash_flow_detail: list[CashFlowDetailRow] = field(default_factory=list)
    reclassifications: list[ReclassificationRow] = field(default_factory=list)

"""财务报表数据模型: ReportType, ReportItem, Report。

这些是项目的核心数据模型，所有模块通过它们通信。
Report 对象不关心数据来源（Excel导入、PDF导入、自动生成），只表示"一张报表"。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ReportType(Enum):
    """财务报表类型。"""

    BALANCE_SHEET = "资产负债表"
    INCOME_STATEMENT = "利润表"
    CASH_FLOW_STATEMENT = "现金流量表"
    # V1:
    STATEMENT_OF_CHANGES_IN_EQUITY = "所有者权益变动表"
    NOTES = "附注"


@dataclass(frozen=True)
class ReportItem:
    """报表中的一个项目（科目/合计项）。

    Attributes:
        key: 公式变量名，与规则公式中的变量一一对应，如 "asset_total"
        name: 显示名称（中文），如 "资产总计"
        amount: 金额（元）。用 float 存储，容差比较处理精度问题。
        beginning_amount: 期初/上期金额（元）。None 表示报表无第二列金额。
        row: 在源文件中的行号（从1开始），用于差异追溯
        column: 在源文件中的列名，如 "期末余额"
    """

    key: str
    name: str
    amount: float
    beginning_amount: float | None = None
    row: int = 0
    column: str = ""

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("ReportItem.key 不能为空")
        if not self.name:
            raise ValueError("ReportItem.name 不能为空")
        if self.amount is None:
            raise ValueError(f"ReportItem「{self.name}」的金额不能为 None")
        if self.row < 0:
            raise ValueError(f"ReportItem「{self.name}」的行号不能为负数: {self.row}")


@dataclass
class Report:
    """一张财务报表。

    包含多个 ReportItem，按 key 索引。
    构造时校验 key 唯一性（违反则抛 DuplicateItemError）。

    Attributes:
        report_type: 报表类型
        period: 报告期间，如 "2024-12"
        source_file: 源文件路径
        items: 报表项目列表
        unmapped_names: 导入时未能映射为标准科目的项目名称（有金额但无法识别），
            供 Agent 工具与人工排查使用；不参与校验
    """

    report_type: ReportType
    period: str = ""
    source_file: str = ""
    items: list[ReportItem] = field(default_factory=list)
    unmapped_names: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._index: dict[str, ReportItem] = {}
        for item in self.items:
            if item.key in self._index:
                from fsa.core.exceptions import DuplicateItemError

                raise DuplicateItemError(item.key, self.report_type.value)
            self._index[item.key] = item

    def get_item(self, key: str) -> ReportItem | None:
        """按 key 查找项目。未找到返回 None。"""
        return self._index.get(key)

    def get_amount(self, key: str) -> float | None:
        """按 key 获取金额。未找到返回 None。"""
        item = self._index.get(key)
        return item.amount if item is not None else None

    def add_item(self, item: ReportItem) -> None:
        """添加一个项目。key 重复则抛 DuplicateItemError。"""
        if item.key in self._index:
            from fsa.core.exceptions import DuplicateItemError

            raise DuplicateItemError(item.key, self.report_type.value)
        self.items.append(item)
        self._index[item.key] = item

    @property
    def item_keys(self) -> list[str]:
        """所有项目的 key 列表。"""
        return list(self._index.keys())

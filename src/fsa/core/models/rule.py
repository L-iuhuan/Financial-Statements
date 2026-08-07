"""勾稽校验规则数据模型: ToleranceType, Severity, ReconciliationRule。

一条规则 = 公式 + 容差类型 + 容差值 + 严重级别。
规则的 evaluate 方法接收 ValidationContext，返回 ValidationResult。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ToleranceType(Enum):
    """容差比较类型。"""

    EXACT = "exact"
    ABSOLUTE = "absolute"
    RELATIVE = "relative"
    THRESHOLD = "threshold"


class Severity(Enum):
    """规则严重级别。"""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class ReconciliationRule:
    """一条勾稽校验规则。

    Attributes:
        rule_id: 规则编号，如 "BS-BAL-001"
        name: 规则名称（中文），如 "资产=负债+所有者权益"
        category: 规则分类，如 "A-表内平衡"
        statements: 涉及的报表类型（中文名列表）
        formula: 校验公式，如 "asset_total == liability_total + equity_total"
        tolerance_type: 容差比较类型
        tolerance: 容差值
        severity: 严重级别
        cas_ref: CAS 准则引用
        notes: 备注说明
    """

    rule_id: str
    name: str
    category: str
    statements: list[str]
    formula: str
    tolerance_type: ToleranceType
    tolerance: float
    severity: Severity
    cas_ref: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.rule_id:
            raise ValueError("规则编号不能为空")
        if not self.formula:
            raise ValueError(f"规则 {self.rule_id} 的公式不能为空")
        if self.tolerance < 0:
            raise ValueError(f"规则 {self.rule_id} 的容差不能为负数: {self.tolerance}")

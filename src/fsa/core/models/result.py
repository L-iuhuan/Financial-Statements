"""校验结果数据模型: ValidationResult, ValidationContext。

ValidationContext 是一次校验运行的上下文，包含所有报表。
ValidationResult 是一条规则的校验结果。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fsa.core.models.report import Report, ReportType
from fsa.core.models.rule import ReconciliationRule, Severity


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

    def build_namespace(self, statement_names: list[str]) -> dict[str, float]:
        """根据规则涉及的报表类型，构建变量命名空间。

        将相关报表中的所有 ReportItem 的 key->amount 映射合并到一个字典中。
        如果同一个 key 在多张报表中出现，抛出 ValueError。

        Args:
            statement_names: 规则涉及的报表中文名列表，如 ["资产负债表"]

        Returns:
            变量命名空间，如 {"asset_total": 1000000.0, "liability_total": 600000.0}

        Raises:
            KeyError: 指定的报表类型不存在
            ValueError: 变量名冲突（同一 key 出现在多张报表中）
        """
        namespace: dict[str, float] = {}
        name_to_type = {rt.value: rt for rt in ReportType}

        for stmt_name in statement_names:
            report_type = name_to_type.get(stmt_name)
            if report_type is None:
                continue
            report = self.reports.get(report_type)
            if report is None:
                continue
            for item in report.items:
                if item.key in namespace:
                    raise ValueError(
                        f"变量「{item.key}」在多张报表中重复定义"
                    )
                namespace[item.key] = item.amount
        return namespace

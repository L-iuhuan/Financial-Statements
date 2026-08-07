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
        errored: 是否因异常而未能完成校验（缺失科目、公式错误等）
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
            message=f"{rule.name}: 无法执行校验 — {error_message}",
            errored=True,
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

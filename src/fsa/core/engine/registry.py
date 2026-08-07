"""规则注册表: 管理启用的勾稽校验规则集合。"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from fsa.core.engine.rule_loader import load_rules_from_json
from fsa.core.models.report import ReportType
from fsa.core.models.rule import ReconciliationRule, Severity

_REPORT_TYPE_NAMES: dict[ReportType, str] = {
    ReportType.BALANCE_SHEET: "资产负债表",
    ReportType.INCOME_STATEMENT: "利润表",
    ReportType.CASH_FLOW_STATEMENT: "现金流量表",
}


class RuleRegistry:
    """管理一组规则，支持启用/禁用、按分类/报表类型/严重级别过滤。"""

    def __init__(self, rules: list[ReconciliationRule]) -> None:
        self._rules: dict[str, ReconciliationRule] = {r.rule_id: r for r in rules}
        self._disabled: set[str] = set()

    @classmethod
    def from_json(cls, file_path: str | Path) -> "RuleRegistry":
        """从 JSON 规则库文件创建注册表。"""
        return cls(load_rules_from_json(file_path))

    def get_all(self) -> list[ReconciliationRule]:
        """返回所有规则（含已禁用的）。"""
        return list(self._rules.values())

    def get_active(self) -> list[ReconciliationRule]:
        """返回启用的规则。"""
        return [r for r in self._rules.values() if r.rule_id not in self._disabled]

    def get_by_id(self, rule_id: str) -> ReconciliationRule | None:
        """按规则编号查找。"""
        return self._rules.get(rule_id)

    def get_by_category(self, category: str) -> list[ReconciliationRule]:
        """按分类过滤。"""
        return [r for r in self._rules.values() if r.category == category]

    def get_by_severity(self, severity: Severity) -> list[ReconciliationRule]:
        """按严重级别过滤。"""
        return [r for r in self._rules.values() if r.severity is severity]

    def get_for_report_types(
        self, report_types: list[ReportType]
    ) -> list[ReconciliationRule]:
        """返回涉及这些报表类型的规则。"""
        names = {_REPORT_TYPE_NAMES[rt] for rt in report_types if rt in _REPORT_TYPE_NAMES}
        if not names:
            return []
        return [
            r for r in self._rules.values() if set(r.statements).intersection(names)
        ]

    def enable(self, rule_id: str) -> bool:
        """启用一条规则。找到并启用返回 True。"""
        if rule_id not in self._rules:
            return False
        self._disabled.discard(rule_id)
        return True

    def disable(self, rule_id: str) -> bool:
        """禁用一条规则。找到并禁用返回 True。"""
        if rule_id not in self._rules:
            return False
        self._disabled.add(rule_id)
        return True

    def enable_all(self) -> None:
        """启用所有规则。"""
        self._disabled.clear()

    def disable_all(self) -> None:
        """禁用所有规则。"""
        self._disabled = set(self._rules.keys())

    def set_tolerance(self, rule_id: str, tolerance: float) -> bool:
        """修改某条规则的容差。成功返回 True。"""
        rule = self._rules.get(rule_id)
        if rule is None:
            return False
        self._rules[rule_id] = replace(rule, tolerance=tolerance)
        return True

    def count(self) -> int:
        """规则总数。"""
        return len(self._rules)

    def active_count(self) -> int:
        """启用规则数。"""
        return len(self.get_active())

    def summary(self) -> dict[str, int]:
        """返回统计摘要。"""
        return {
            "total": self.count(),
            "active": self.active_count(),
            "error": self._count_by_severity(Severity.ERROR),
            "warning": self._count_by_severity(Severity.WARNING),
            "info": self._count_by_severity(Severity.INFO),
        }

    def _count_by_severity(self, severity: Severity) -> int:
        """统计指定严重级别的规则数。"""
        return sum(1 for r in self._rules.values() if r.severity is severity)

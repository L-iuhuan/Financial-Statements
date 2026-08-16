"""RuleRegistry 的单元测试。"""

from __future__ import annotations

from pathlib import Path

from fsa.core.engine.registry import RuleRegistry
from fsa.core.models.report import ReportType
from fsa.core.models.rule import ReconciliationRule, Severity, ToleranceType

RULE_LIBRARY = (
    Path(__file__).resolve().parent.parent.parent / "cas_gouji_rule_library.json"
)


def make_rule(
    rule_id: str = "X-001",
    category: str = "A-表内平衡",
    statements: list[str] | None = None,
    severity: Severity = Severity.ERROR,
    tolerance: float = 0.01,
) -> ReconciliationRule:
    """创建一条测试规则。"""
    return ReconciliationRule(
        rule_id=rule_id,
        name=f"规则{rule_id}",
        category=category,
        statements=statements or ["资产负债表"],
        formula="a == b",
        tolerance_type=ToleranceType.EXACT,
        tolerance=tolerance,
        severity=severity,
    )


def make_registry() -> RuleRegistry:
    """创建包含三条规则的注册表。"""
    rules = [
        make_rule("A-001", category="A-表内平衡", severity=Severity.ERROR),
        make_rule(
            "B-001",
            category="B-表间勾稽",
            statements=["资产负债表", "利润表"],
            severity=Severity.WARNING,
        ),
        make_rule(
            "C-001",
            category="C-逻辑合理性",
            statements=["现金流量表"],
            severity=Severity.INFO,
        ),
    ]
    return RuleRegistry(rules)


class TestConstruction:
    """注册表构造。"""

    def test_create_from_rule_list(self) -> None:
        reg = make_registry()
        assert reg.count() == 3

    def test_from_json_loads_real_file(self) -> None:
        reg = RuleRegistry.from_json(RULE_LIBRARY)
        assert reg.count() == 42
        assert reg.active_count() == 42

    def test_empty_registry(self) -> None:
        reg = RuleRegistry([])
        assert reg.count() == 0
        assert reg.get_all() == []
        assert reg.summary() == {"total": 0, "active": 0, "error": 0, "warning": 0, "info": 0}


class TestQuery:
    """查询方法。"""

    def test_get_all_returns_all(self) -> None:
        reg = make_registry()
        assert len(reg.get_all()) == 3

    def test_get_active_returns_enabled_only(self) -> None:
        reg = make_registry()
        reg.disable("B-001")
        active = reg.get_active()
        assert [r.rule_id for r in active] == ["A-001", "C-001"]

    def test_get_by_id_found(self) -> None:
        reg = make_registry()
        rule = reg.get_by_id("B-001")
        assert rule is not None
        assert rule.rule_id == "B-001"

    def test_get_by_id_not_found(self) -> None:
        reg = make_registry()
        assert reg.get_by_id("NOPE") is None

    def test_get_by_category(self) -> None:
        reg = make_registry()
        a = reg.get_by_category("A-表内平衡")
        assert [r.rule_id for r in a] == ["A-001"]
        b = reg.get_by_category("B-表间勾稽")
        assert [r.rule_id for r in b] == ["B-001"]
        c = reg.get_by_category("C-逻辑合理性")
        assert [r.rule_id for r in c] == ["C-001"]
        assert reg.get_by_category("Z-不存在") == []

    def test_get_by_severity(self) -> None:
        reg = make_registry()
        assert [r.rule_id for r in reg.get_by_severity(Severity.ERROR)] == ["A-001"]
        assert [r.rule_id for r in reg.get_by_severity(Severity.WARNING)] == ["B-001"]
        assert [r.rule_id for r in reg.get_by_severity(Severity.INFO)] == ["C-001"]

    def test_get_for_report_types_balance_sheet(self) -> None:
        reg = make_registry()
        rules = reg.get_for_report_types([ReportType.BALANCE_SHEET])
        # A-001 和 B-001 涉及资产负债表; C-001 仅现金流量表
        assert {r.rule_id for r in rules} == {"A-001", "B-001"}

    def test_get_for_report_types_bs_and_is(self) -> None:
        reg = make_registry()
        rules = reg.get_for_report_types(
            [ReportType.BALANCE_SHEET, ReportType.INCOME_STATEMENT]
        )
        assert {r.rule_id for r in rules} == {"A-001", "B-001"}

    def test_get_for_report_types_all_three(self) -> None:
        reg = make_registry()
        rules = reg.get_for_report_types(
            [
                ReportType.BALANCE_SHEET,
                ReportType.INCOME_STATEMENT,
                ReportType.CASH_FLOW_STATEMENT,
            ]
        )
        assert {r.rule_id for r in rules} == {"A-001", "B-001", "C-001"}

    def test_get_for_report_types_empty(self) -> None:
        reg = make_registry()
        assert reg.get_for_report_types([]) == []


class TestEnableDisable:
    """启用/禁用。"""

    def test_disable_returns_true(self) -> None:
        reg = make_registry()
        assert reg.disable("A-001") is True
        assert reg.active_count() == 2

    def test_disable_unknown_returns_false(self) -> None:
        reg = make_registry()
        assert reg.disable("NOPE") is False

    def test_enable_returns_true(self) -> None:
        reg = make_registry()
        reg.disable("A-001")
        assert reg.enable("A-001") is True
        assert reg.active_count() == 3

    def test_enable_unknown_returns_false(self) -> None:
        reg = make_registry()
        assert reg.enable("NOPE") is False

    def test_enable_all(self) -> None:
        reg = make_registry()
        reg.disable_all()
        assert reg.active_count() == 0
        reg.enable_all()
        assert reg.active_count() == 3

    def test_disable_all(self) -> None:
        reg = make_registry()
        reg.disable_all()
        assert reg.active_count() == 0
        assert reg.get_active() == []


class TestSetTolerance:
    """容差修改。"""

    def test_set_tolerance_returns_true_and_changes(self) -> None:
        reg = make_registry()
        assert reg.set_tolerance("A-001", 2.5) is True
        rule = reg.get_by_id("A-001")
        assert rule is not None
        assert rule.tolerance == 2.5

    def test_set_tolerance_unknown_returns_false(self) -> None:
        reg = make_registry()
        assert reg.set_tolerance("NOPE", 2.5) is False

    def test_set_tolerance_preserves_other_fields(self) -> None:
        reg = make_registry()
        reg.set_tolerance("A-001", 9.9)
        rule = reg.get_by_id("A-001")
        assert rule is not None
        assert rule.rule_id == "A-001"
        assert rule.category == "A-表内平衡"
        assert rule.formula == "a == b"
        assert rule.severity is Severity.ERROR

    def test_set_tolerance_does_not_affect_others(self) -> None:
        reg = make_registry()
        reg.set_tolerance("A-001", 9.9)
        other = reg.get_by_id("B-001")
        assert other is not None
        assert other.tolerance == 0.01


class TestSummary:
    """统计信息。"""

    def test_count(self) -> None:
        reg = make_registry()
        assert reg.count() == 3

    def test_active_count(self) -> None:
        reg = make_registry()
        reg.disable("B-001")
        assert reg.active_count() == 2

    def test_summary(self) -> None:
        reg = make_registry()
        summary = reg.summary()
        assert summary == {"total": 3, "active": 3, "error": 1, "warning": 1, "info": 1}

    def test_summary_reflects_disabled(self) -> None:
        reg = make_registry()
        reg.disable("A-001")
        summary = reg.summary()
        assert summary["total"] == 3
        assert summary["active"] == 2
        assert summary["error"] == 1
        assert summary["warning"] == 1
        assert summary["info"] == 1

    def test_summary_real_file(self) -> None:
        reg = RuleRegistry.from_json(RULE_LIBRARY)
        summary = reg.summary()
        assert summary["total"] == 42
        assert summary["active"] == 42
        assert summary["error"] > 0
        assert summary["warning"] > 0
        # v1.1 规则库删除了唯一的 INFO 规则 (LR-FIX-001), 当前无 INFO 级规则
        assert summary["info"] == 0
        assert (
            summary["error"] + summary["warning"] + summary["info"] == 42
        )

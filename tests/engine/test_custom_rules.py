"""自定义规则: 注册表增删 + 持久化往返测试。"""

from __future__ import annotations

from fsa.core.engine.custom_rules import load_custom_rules, save_custom_rules
from fsa.core.engine.registry import RuleRegistry
from fsa.core.models.rule import ReconciliationRule, Severity, ToleranceType


def _make_custom(rule_id: str = "CUST-001") -> ReconciliationRule:
    return ReconciliationRule(
        rule_id=rule_id,
        name="自定义测试规则",
        category="C-逻辑合理性",
        statements=["资产负债表"],
        formula="asset_total == liability_total + equity_total",
        tolerance_type=ToleranceType.EXACT,
        tolerance=0.01,
        severity=Severity.WARNING,
    )


class TestRegistryCustomRules:
    """RuleRegistry 自定义规则增删。"""

    def test_add_rule_success(self) -> None:
        reg = RuleRegistry([])
        assert reg.add_rule(_make_custom(), custom=True) is True
        assert reg.get_by_id("CUST-001") is not None
        assert reg.is_custom("CUST-001") is True

    def test_add_rule_duplicate_rejected(self) -> None:
        reg = RuleRegistry([_make_custom("BS-BAL-001")])
        assert reg.add_rule(_make_custom("BS-BAL-001")) is False

    def test_remove_custom_rule(self) -> None:
        reg = RuleRegistry([])
        reg.add_rule(_make_custom(), custom=True)
        assert reg.remove_rule("CUST-001") is True
        assert reg.get_by_id("CUST-001") is None

    def test_remove_builtin_rule_rejected(self) -> None:
        reg = RuleRegistry([_make_custom("BS-BAL-001")])
        assert reg.remove_rule("BS-BAL-001") is False
        assert reg.get_by_id("BS-BAL-001") is not None


class TestCustomRulesPersistence:
    """custom_rules.json 持久化往返。"""

    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(
            "fsa.core.engine.custom_rules._custom_rules_path",
            lambda: tmp_path / "custom_rules.json",
        )
        save_custom_rules([_make_custom("CUST-001"), _make_custom("CUST-002")])
        loaded = load_custom_rules()
        assert {r.rule_id for r in loaded} == {"CUST-001", "CUST-002"}
        assert loaded[0].name == "自定义测试规则"
        assert loaded[0].tolerance_type is ToleranceType.EXACT

    def test_load_missing_file_returns_empty(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(
            "fsa.core.engine.custom_rules._custom_rules_path",
            lambda: tmp_path / "nonexistent.json",
        )
        assert load_custom_rules() == []

    def test_load_corrupt_file_returns_empty(self, tmp_path, monkeypatch) -> None:
        bad = tmp_path / "custom_rules.json"
        bad.write_text("{invalid json", encoding="utf-8")
        monkeypatch.setattr(
            "fsa.core.engine.custom_rules._custom_rules_path",
            lambda: bad,
        )
        assert load_custom_rules() == []


class TestCustomRuleValidation:
    """自定义规则公式校验 (对话框逻辑)。"""

    def test_valid_equality_formula(self, qapp, qtbot) -> None:
        from fsa.gui.widgets.custom_rule_dialog import CustomRuleDialog
        dlg = CustomRuleDialog()
        qtbot.addWidget(dlg)
        assert dlg._validate_formula("a == b + c") is None

    def test_valid_threshold_formula(self, qapp, qtbot) -> None:
        from fsa.gui.widgets.custom_rule_dialog import CustomRuleDialog
        dlg = CustomRuleDialog()
        qtbot.addWidget(dlg)
        assert dlg._validate_formula("liability_total / asset_total <= 0.85") is None

    def test_invalid_formula_rejected(self, qapp, qtbot) -> None:
        from fsa.gui.widgets.custom_rule_dialog import CustomRuleDialog
        dlg = CustomRuleDialog()
        qtbot.addWidget(dlg)
        result = dlg._validate_formula("a ==@@@")
        assert result is not None
        assert "错误" in result or "语法" in result

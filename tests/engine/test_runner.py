"""RuleRunner 的单元测试。"""

from __future__ import annotations

import pytest

from fsa.core.engine.runner import RuleRunner
from fsa.core.models.rule import ReconciliationRule, Severity, ToleranceType
from tests.conftest import make_context, make_rule_bs_bal_001


class TestRuleRunner:
    """RuleRunner 测试。"""

    def test_balanced_returns_pass(self) -> None:
        """平衡: 资产=100, 负债=60, 权益=40 -> 通过。"""
        rule = make_rule_bs_bal_001()
        ctx = make_context(asset_total=100.0, liability_total=60.0, equity_total=40.0)
        result = RuleRunner.run(rule, ctx)
        assert result.passed is True
        assert result.diff == pytest.approx(0.0)

    def test_unbalanced_returns_fail(self) -> None:
        """不平衡: 资产=100, 负债=60, 权益=35 -> 不通过, diff=5。"""
        rule = make_rule_bs_bal_001()
        ctx = make_context(asset_total=100.0, liability_total=60.0, equity_total=35.0)
        result = RuleRunner.run(rule, ctx)
        assert result.passed is False
        assert result.diff == pytest.approx(5.0)

    def test_all_zero_returns_pass(self) -> None:
        """全零: 资产=0, 负债=0, 权益=0 -> 通过。"""
        rule = make_rule_bs_bal_001()
        ctx = make_context(asset_total=0.0, liability_total=0.0, equity_total=0.0)
        result = RuleRunner.run(rule, ctx)
        assert result.passed is True

    def test_all_negative_returns_pass(self) -> None:
        """全负: 资产=-100, 负债=-60, 权益=-40 -> 通过。"""
        rule = make_rule_bs_bal_001()
        ctx = make_context(asset_total=-100.0, liability_total=-60.0, equity_total=-40.0)
        result = RuleRunner.run(rule, ctx)
        assert result.passed is True

    def test_large_numbers_pass(self) -> None:
        """大数: 1e15级别。"""
        rule = make_rule_bs_bal_001()
        ctx = make_context(
            asset_total=1e15, liability_total=6e14, equity_total=4e14
        )
        result = RuleRunner.run(rule, ctx)
        assert result.passed is True

    def test_float_precision_within_tolerance(self) -> None:
        """浮点精度: 0.1+0.2!=0.3 但容差内通过。"""
        rule = make_rule_bs_bal_001()
        ctx = make_context(
            asset_total=0.3, liability_total=0.1, equity_total=0.2
        )
        result = RuleRunner.run(rule, ctx)
        assert result.passed is True

    def test_result_fields_populated(self) -> None:
        """结果字段完整性检查。"""
        rule = make_rule_bs_bal_001()
        ctx = make_context(asset_total=100.0, liability_total=60.0, equity_total=40.0)
        result = RuleRunner.run(rule, ctx)
        assert result.rule_id == "BS-BAL-001"
        assert result.rule_name == "资产=负债+所有者权益"
        assert result.severity == Severity.ERROR
        assert result.tolerance == 0.01
        assert "asset_total == liability_total + equity_total" in result.formula
        assert result.left_value == 100.0
        assert result.right_value == 100.0

    def test_pass_message_contains_通过(self) -> None:
        """通过消息包含'通过'。"""
        rule = make_rule_bs_bal_001()
        ctx = make_context(asset_total=100.0, liability_total=60.0, equity_total=40.0)
        result = RuleRunner.run(rule, ctx)
        assert "通过" in result.message

    def test_fail_message_contains_diff(self) -> None:
        """失败消息包含差额和'不通过'。"""
        rule = make_rule_bs_bal_001()
        ctx = make_context(asset_total=100.0, liability_total=60.0, equity_total=35.0)
        result = RuleRunner.run(rule, ctx)
        assert "不通过" in result.message
        assert "5.00" in result.message

    def test_warning_severity_in_message(self) -> None:
        """warning 严重级别在消息中显示为'警告'。"""
        rule = ReconciliationRule(
            rule_id="TEST-W-001",
            name="测试警告规则",
            category="C-逻辑合理性",
            statements=["资产负债表"],
            formula="asset_total == liability_total + equity_total",
            tolerance_type=ToleranceType.EXACT,
            tolerance=0.01,
            severity=Severity.WARNING,
        )
        ctx = make_context(asset_total=100.0, liability_total=60.0, equity_total=35.0)
        result = RuleRunner.run(rule, ctx)
        assert "警告" in result.message

    def test_equality_rule_result_has_category(self) -> None:
        """等式规则结果包含 category。"""
        rule = make_rule_bs_bal_001()
        ctx = make_context(asset_total=100.0, liability_total=60.0, equity_total=40.0)
        result = RuleRunner.run(rule, ctx)
        assert result.category == "A-表内平衡"

    def test_equality_rule_result_has_trace(self) -> None:
        """等式规则结果包含 trace 列表。"""
        rule = make_rule_bs_bal_001()
        ctx = make_context(asset_total=100.0, liability_total=60.0, equity_total=40.0)
        result = RuleRunner.run(rule, ctx)
        assert len(result.trace) >= 3
        keys = {t.key for t in result.trace}
        assert "asset_total" in keys
        assert "liability_total" in keys
        assert "equity_total" in keys

    def test_trace_items_have_side(self) -> None:
        """trace 中左侧变量 side='left'，右侧变量 side='right'。"""
        rule = make_rule_bs_bal_001()
        ctx = make_context(asset_total=100.0, liability_total=60.0, equity_total=40.0)
        result = RuleRunner.run(rule, ctx)
        left_vars = [t for t in result.trace if t.side == "left"]
        right_vars = [t for t in result.trace if t.side == "right"]
        assert len(left_vars) >= 1
        assert len(right_vars) >= 1
        assert any(t.key == "asset_total" for t in left_vars)
        assert any(t.key == "liability_total" for t in right_vars)

    def test_trace_items_have_names_and_amounts(self) -> None:
        """trace 项包含科目名和金额。"""
        rule = make_rule_bs_bal_001()
        ctx = make_context(asset_total=100.0, liability_total=60.0, equity_total=40.0)
        result = RuleRunner.run(rule, ctx)
        for t in result.trace:
            assert t.name != ""
            assert isinstance(t.amount, float)

    def test_threshold_rule_result_has_trace(self) -> None:
        """阈值规则结果也包含 trace。"""
        rule = ReconciliationRule(
            rule_id="TEST-TH-001",
            name="资产负债率",
            category="C-逻辑合理性",
            statements=["资产负债表"],
            formula="liability_total / asset_total <= 0.85",
            tolerance_type=ToleranceType.THRESHOLD,
            tolerance=0.0,
            severity=Severity.WARNING,
        )
        ctx = make_context(asset_total=100.0, liability_total=60.0, equity_total=40.0)
        result = RuleRunner.run(rule, ctx)
        assert len(result.trace) >= 2
        keys = {t.key for t in result.trace}
        assert "asset_total" in keys
        assert "liability_total" in keys

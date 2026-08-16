"""ValidationContext.build_namespace 缓存测试 (FIX 2 - H1 namespace 缓存)。

验证:
- 相同 statement_names 返回的 namespace 值一致 (共享缓存)
- 不同 statement_names 各自缓存
- runner 不修改缓存 (复制后更新)
- 阈值变量不泄漏到后续规则
- 缓存不影响校验结果正确性 (P2 确定性)
"""

from __future__ import annotations

import pytest

from fsa.core.engine.runner import RuleRunner
from fsa.core.models.result import ValidationContext
from fsa.core.models.rule import ReconciliationRule, Severity, ToleranceType
from tests.conftest import make_balance_sheet, make_context, make_rule_bs_bal_001


class TestNamespaceCacheIdentity:
    """相同 statements 返回相同对象 (缓存命中)。"""

    def test_same_statements_same_namespace(self) -> None:
        """两次 build_namespace 相同参数返回相同 dict 对象 (缓存命中)。"""
        ctx = make_context(asset_total=100.0, liability_total=60.0, equity_total=40.0)
        ns1 = ctx.build_namespace(["资产负债表"])
        ns2 = ctx.build_namespace(["资产负债表"])
        assert ns1 is ns2  # 同一对象 = 缓存命中
        assert ns1["asset_total"] == 100.0

    def test_different_statements_different_cache(self) -> None:
        """不同 statements 各自缓存。"""
        ctx = make_context(asset_total=100.0, liability_total=60.0, equity_total=40.0)
        ns_bs = ctx.build_namespace(["资产负债表"])
        ns_bs_is = ctx.build_namespace(["资产负债表", "利润表"])
        assert ns_bs is not ns_bs_is
        # 各自可重复命中
        assert ctx.build_namespace(["资产负债表"]) is ns_bs
        assert ctx.build_namespace(["资产负债表", "利润表"]) is ns_bs_is


class TestNamespaceCacheNoMutation:
    """runner 不修改缓存; 阈值变量不泄漏。"""

    def test_runner_copies_before_mutate(self) -> None:
        """runner 复制 namespace 后更新阈值变量, 缓存不受影响。"""
        ctx = make_context(asset_total=100.0, liability_total=60.0, equity_total=40.0)

        rule = ReconciliationRule(
            rule_id="LR-TEST-001",
            name="资产负债率测试",
            category="C-逻辑合理性",
            statements=["资产负债表"],
            formula="liability_total / asset_total <= dar_threshold",
            tolerance_type=ToleranceType.THRESHOLD,
            tolerance=0.0,
            severity=Severity.WARNING,
        )

        threshold_vars = {"dar_threshold": 0.5}
        RuleRunner.run(rule, ctx, threshold_vars=threshold_vars)

        # 缓存不应包含阈值变量
        ns = ctx.build_namespace(["资产负债表"])
        assert "dar_threshold" not in ns

    def test_threshold_override_does_not_leak(self) -> None:
        """先运行带阈值覆写的规则, 再运行不带阈值的规则, 后者看到默认值。"""
        ctx = make_context(asset_total=100.0, liability_total=60.0, equity_total=40.0)

        rule = ReconciliationRule(
            rule_id="LR-TEST-002",
            name="资产负债率测试",
            category="C-逻辑合理性",
            statements=["资产负债表"],
            formula="liability_total / asset_total <= dar_threshold",
            tolerance_type=ToleranceType.THRESHOLD,
            tolerance=0.0,
            severity=Severity.WARNING,
        )

        # 第一次: dar_threshold=0.5 (应通过, 60/100=0.6 > 0.5 不通过)
        result1 = RuleRunner.run(rule, ctx, threshold_vars={"dar_threshold": 0.5})
        assert result1.passed is False

        # 第二次: 不带阈值, 应回落 general 默认值 0.85 (60/100=0.6 <= 0.85 通过)
        result2 = RuleRunner.run(rule, ctx)
        assert result2.passed is True

    def test_base_namespace_unchanged_by_runner(self) -> None:
        """runner 执行后, 基础 namespace 缓存不变。"""
        ctx = make_context(asset_total=100.0, liability_total=60.0, equity_total=40.0)
        ns_before = ctx.build_namespace(["资产负债表"])
        keys_before = set(ns_before.keys())
        values_before = dict(ns_before)

        rule = make_rule_bs_bal_001()
        RuleRunner.run(rule, ctx)

        ns_after = ctx.build_namespace(["资产负债表"])
        assert ns_after is ns_before  # 同一对象
        assert set(ns_after.keys()) == keys_before
        assert ns_after == values_before  # 值不变


class TestNamespaceCacheCorrectness:
    """缓存不影响校验结果正确性 (P2 确定性)。"""

    def test_cached_namespace_same_results(self) -> None:
        """缓存命中后校验结果与直接构建一致。"""
        ctx = make_context(asset_total=100.0, liability_total=60.0, equity_total=40.0)
        rule = make_rule_bs_bal_001()

        # 预热缓存
        ctx.build_namespace(["资产负债表"])

        result = RuleRunner.run(rule, ctx)
        assert result.passed is True
        assert result.left_value == 100.0
        assert result.right_value == 100.0
        assert result.diff == pytest.approx(0.0)

    def test_cached_with_two_rules(self) -> None:
        """两条规则共享同一 statements 缓存。"""
        make_context(asset_total=100.0, liability_total=60.0, equity_total=40.0)

        rule1 = make_rule_bs_bal_001()
        rule2 = ReconciliationRule(
            rule_id="BS-BAL-002",
            name="流动+非流动=资产",
            category="A-表内平衡",
            statements=["资产负债表"],
            formula="asset_total == current_assets + non_current_assets",
            tolerance_type=ToleranceType.EXACT,
            tolerance=0.01,
            severity=Severity.ERROR,
        )
        # 添加缺失的科目
        bs = make_balance_sheet(
            asset_total=100.0,
            liability_total=60.0,
            equity_total=40.0,
            current_assets=50.0,
            non_current_assets=50.0,
        )
        ctx2 = ValidationContext(period="2024-12")
        ctx2.add_report(bs)

        r1 = RuleRunner.run(rule1, ctx2)
        r2 = RuleRunner.run(rule2, ctx2)

        assert r1.passed is True
        assert r2.passed is True


class TestNamespaceCacheEmpty:
    """空报表上下文。"""

    def test_empty_context_returns_defaults(self) -> None:
        """无报表时返回预填充 0.0 的 namespace。"""
        ctx = ValidationContext(period="2024-12")
        ns = ctx.build_namespace(["资产负债表"])
        # 预填充了默认值
        assert "asset_total" in ns
        assert ns["asset_total"] == 0.0

    def test_empty_context_cache_hit(self) -> None:
        """空 context 也能缓存命中。"""
        ctx = ValidationContext(period="2024-12")
        ns1 = ctx.build_namespace(["资产负债表"])
        ns2 = ctx.build_namespace(["资产负债表"])
        assert ns1 is ns2

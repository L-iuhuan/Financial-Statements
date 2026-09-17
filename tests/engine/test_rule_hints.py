"""rule_hints 模块测试: 覆盖完整性 + 消息格式 + 指标计算。"""

from __future__ import annotations

from pathlib import Path

from fsa.core.engine.rule_hints import (
    RULE_HINTS,
    format_hint_block,
    format_metric_line,
)
from fsa.core.engine.rule_loader import load_rules_from_json

_RULE_LIBRARY = Path(__file__).resolve().parents[2] / "cas_gouji_rule_library.json"

# 明细勾稽检查的规则 ID (core/engine 的 5 个 *_checks 模块产出)
_DETAIL_RULE_IDS = (
    "JNL-BAL-001",
    "CF-DTL-001",
    "CF-JNL-001",
    "TB-BS-001",
    "CF-CLS-001",
    "CF-CLS-002",
    "CF-CLS-003",
    "CF-CLS-004",
    "CF-CLS-005",
    "CF-CLS-006",
    "CF-CLS-007",
    "CF-CLS-008",
    "CF-CLS-901",
    "RC-001",
    "RC-002",
    "RP-001",
    "SAL-001",
    "SAL-002",
    "ICF-001",
    "ICF-002",
    "RPS-001",
)


class TestHintCoverage:
    """每条规则都有小白解读, 防止新增规则后文案漏配。"""

    def test_every_library_rule_has_hint(self) -> None:
        """规则库 42 条全部有 RuleHint。"""
        rules = load_rules_from_json(_RULE_LIBRARY)
        missing = [rule.rule_id for rule in rules if rule.rule_id not in RULE_HINTS]
        assert not missing, f"规则库以下规则缺少小白解读: {missing}"

    def test_every_hint_has_why_and_advice(self) -> None:
        """每条解读必须含「为什么关注」与「建议」(用户核心诉求)。"""
        incomplete = [
            rule_id
            for rule_id, hint in RULE_HINTS.items()
            if not hint.why or not hint.advice
        ]
        assert not incomplete, f"以下规则解读缺少 why/advice: {incomplete}"

    def test_detail_rule_ids_have_hint(self) -> None:
        """全部明细勾稽规则 ID 有解读。"""
        missing = [rule_id for rule_id in _DETAIL_RULE_IDS if rule_id not in RULE_HINTS]
        assert not missing, f"明细规则缺少小白解读: {missing}"

    def test_metric_expr_rules_have_label_and_format(self) -> None:
        """配置了指标表达式的规则必须有中文名与格式。"""
        incomplete = [
            rule_id
            for rule_id, hint in RULE_HINTS.items()
            if hint.metric_expr and (not hint.metric_label or hint.metric_format not in ("percent", "currency", "number"))
        ]
        assert not incomplete, f"以下规则指标缺少 label/format: {incomplete}"


class TestFormatHintBlock:
    """未通过消息的解读块格式。"""

    def test_warning_block_contains_severity_meaning_and_sections(self) -> None:
        """警告级解读含级别说明与四个小节。"""
        block = format_hint_block("LR-DAR-001", "warning")
        assert "【级别说明】" in block
        assert "异常不等于做错账" in block
        assert "【为什么关注】" in block
        assert "【常见原因】" in block
        assert "【建议】" in block

    def test_error_block_says_must_fix(self) -> None:
        """错误级解读明确「必须改正」。"""
        block = format_hint_block("BS-BAL-001", "error")
        assert "必须改正" in block

    def test_unknown_rule_returns_severity_only(self) -> None:
        """未收录规则只返回级别说明 (自定义规则兜底)。"""
        block = format_hint_block("CUSTOM-001", "warning")
        assert "【级别说明】" in block
        assert "【为什么关注】" not in block

    def test_unknown_severity_and_rule_returns_empty(self) -> None:
        """规则与级别都未收录时返回空串 (不污染消息)。"""
        assert format_hint_block("CUSTOM-001", "unknown") == ""


class TestFormatMetricLine:
    """阈值类规则的实际值指标行。"""

    def test_percent_metric_renders_with_dynamic_criterion(self) -> None:
        """资产负债率: 实际值百分比 + 行业阈值动态判断标准。"""
        line = format_metric_line(
            "LR-DAR-001",
            {"liability_total": 88.0, "asset_total": 100.0},
            {"dar_threshold": 0.85},
        )
        assert "资产负债率 = 88.0%" in line
        assert "不超过 85%" in line

    def test_number_metric_renders_threshold(self) -> None:
        """流动比率: 数字格式与阈值数字格式。"""
        line = format_metric_line(
            "LR-QUICK-001",
            {"current_assets": 80.0, "current_liabilities": 100.0},
            {"current_ratio_threshold": 1.0},
        )
        assert "流动比率 = 0.80" in line
        assert "不低于 1.00" in line

    def test_currency_metric_renders_yuan(self) -> None:
        """金额类指标带千分位与「元」。"""
        line = format_metric_line("LR-OCF-001", {"operating_net": -1234567.5})
        assert "经营活动净现金流量 = -1,234,567.50 元" in line

    def test_missing_variable_returns_empty(self) -> None:
        """变量缺失时返回空串 (P1: 不影响判定, 不抛异常)。"""
        assert format_metric_line("LR-DAR-001", {}) == ""

    def test_rule_without_metric_returns_empty(self) -> None:
        """等式规则无指标表达式时返回空串。"""
        assert format_metric_line("BS-BAL-001", {"asset_total": 100.0}) == ""

    def test_zero_division_returns_empty(self) -> None:
        """分母为零时返回空串 (不向调用方抛异常)。"""
        assert format_metric_line(
            "LR-DAR-001", {"liability_total": 10.0, "asset_total": 0.0}
        ) == ""

    def test_static_criterion_fallback(self) -> None:
        """无行业阈值变量时回退静态判断标准文案。"""
        line = format_metric_line(
            "LR-GM-001", {"revenue": 100.0, "operating_cost": 60.0}
        )
        assert "毛利率 = 40.0%" in line
        assert "0%～100%" in line

    def test_sales_cash_ratio_criterion_direction_min(self) -> None:
        """销售收现比为「不低于」阈值 (方向显式声明, oracle 评审阻断项回归)。"""
        line = format_metric_line(
            "LR-SALES-001",
            {"cash_received_from_sales": 60.0, "revenue": 100.0},
            {"sales_cash_ratio_threshold": 0.8},
        )
        assert "销售收现比 = 60.0%" in line
        assert "不低于 80%" in line
        assert "不超过" not in line

    def test_non_integer_percent_threshold_keeps_decimal(self) -> None:
        """非整百分比阈值保留一位小数 (0.355 -> 35.5%, 展示与判定一致)。"""
        line = format_metric_line(
            "LR-DAR-001",
            {"liability_total": 40.0, "asset_total": 100.0},
            {"dar_threshold": 0.355},
        )
        assert "35.5%" in line


class TestEndToEndMessage:
    """经 RuleRunner 的消息必须包含解读且不泄露原始公式变量。"""

    def test_threshold_failure_message_includes_hint_and_metric(self) -> None:
        from fsa.core.engine.registry import RuleRegistry
        from fsa.core.engine.runner import RuleRunner
        from fsa.core.engine.thresholds import threshold_vars_for
        from tests.conftest import make_context

        registry = RuleRegistry(load_rules_from_json(_RULE_LIBRARY))
        rule = registry.get_by_id("LR-DAR-001")
        assert rule is not None
        context = make_context(asset_total=100.0, liability_total=88.0, equity_total=12.0)
        result = RuleRunner.run(rule, context, threshold_vars_for("general"))

        assert result.passed is False
        assert "【实际值】" in result.message
        assert "【为什么关注】" in result.message
        assert "liability_total" not in result.message
        assert "dar_threshold" not in result.message

    def test_equality_failure_message_includes_hint(self) -> None:
        from fsa.core.engine.registry import RuleRegistry
        from fsa.core.engine.runner import RuleRunner
        from tests.conftest import make_context

        registry = RuleRegistry(load_rules_from_json(_RULE_LIBRARY))
        rule = registry.get_by_id("BS-BAL-001")
        assert rule is not None
        context = make_context(asset_total=100.0, liability_total=60.0, equity_total=30.0)
        result = RuleRunner.run(rule, context)

        assert result.passed is False
        assert "差额: 10.00 元" in result.message
        assert "【为什么关注】" in result.message
        assert "【建议】" in result.message

    def test_passed_message_has_no_hint(self) -> None:
        """通过结果不追加解读 (避免噪音)。"""
        from fsa.core.engine.registry import RuleRegistry
        from fsa.core.engine.runner import RuleRunner
        from tests.conftest import make_context

        registry = RuleRegistry(load_rules_from_json(_RULE_LIBRARY))
        rule = registry.get_by_id("BS-BAL-001")
        assert rule is not None
        context = make_context(asset_total=100.0, liability_total=60.0, equity_total=40.0)
        result = RuleRunner.run(rule, context)

        assert result.passed is True
        assert "【级别说明】" not in result.message

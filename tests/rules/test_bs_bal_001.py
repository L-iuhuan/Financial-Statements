"""BS-BAL-001 规则端到端集成测试。

规则: 资产 = 负债 + 所有者权益
公式: asset_total == liability_total + equity_total
容差: 0.01 元 (EXACT)
严重级别: ERROR

测试覆盖所有边界场景:
- 正常路径、边界值、边界外
- 零值、负值、大数、浮点精度
- 缺失数据、None值、重复key
"""

from __future__ import annotations

import pytest

from fsa.core.exceptions import DuplicateItemError, MissingItemError
from fsa.core.models.report import Report, ReportItem, ReportType
from fsa.core.models.result import ValidationContext
from fsa.core.models.rule import ReconciliationRule, Severity, ToleranceType
from fsa.core.engine.runner import RuleRunner
from tests.conftest import make_balance_sheet, make_rule_bs_bal_001


def make_rule(
    tolerance: float = 0.01,
    severity: Severity = Severity.ERROR,
) -> ReconciliationRule:
    """创建 BS-BAL-001 规则 (可自定义容差和严重级别)。"""
    return ReconciliationRule(
        rule_id="BS-BAL-001",
        name="资产=负债+所有者权益",
        category="A-表内平衡",
        statements=["资产负债表"],
        formula="asset_total == liability_total + equity_total",
        tolerance_type=ToleranceType.EXACT,
        tolerance=tolerance,
        severity=severity,
        cas_ref="《企业会计准则--基本准则》第5条/第43条; 会计恒等式",
        notes="基本平衡关系; 破坏即报表编制错误",
    )


def make_ctx(
    asset_total: float = 100.0,
    liability_total: float = 60.0,
    equity_total: float = 40.0,
) -> ValidationContext:
    """创建包含资产负债表的校验上下文。"""
    bs = make_balance_sheet(
        asset_total=asset_total,
        liability_total=liability_total,
        equity_total=equity_total,
    )
    ctx = ValidationContext(period="2024-12")
    ctx.add_report(bs)
    return ctx


class TestBSBAL001Normal:
    """正常路径测试。"""

    def test_balanced_passes(self) -> None:
        """标准平衡: 100 = 60 + 40 -> 通过。"""
        result = RuleRunner.run(make_rule(), make_ctx(100.0, 60.0, 40.0))
        assert result.passed is True
        assert result.diff == pytest.approx(0.0)

    def test_large_balanced_passes(self) -> None:
        """大数平衡: 1e15 = 6e14 + 4e14 -> 通过。"""
        result = RuleRunner.run(make_rule(), make_ctx(1e15, 6e14, 4e14))
        assert result.passed is True

    def test_decimal_balanced_passes(self) -> None:
        """小数平衡: 100.50 = 60.30 + 40.20 -> 通过。"""
        result = RuleRunner.run(make_rule(), make_ctx(100.50, 60.30, 40.20))
        assert result.passed is True


class TestBSBAL001Boundary:
    """边界值测试。"""

    def test_diff_at_tolerance_passes(self) -> None:
        """差额恰等于容差: diff=1.0, tolerance=1.0 -> 通过。

        用整数避免浮点精度问题 (0.01 在 float 中不可精确表示)。
        """
        rule = make_rule(tolerance=1.0)
        # 101 = 60 + 40 -> diff = 1.0 == tolerance
        result = RuleRunner.run(rule, make_ctx(101.0, 60.0, 40.0))
        assert result.passed is True

    def test_diff_just_over_tolerance_fails(self) -> None:
        """差额刚好超过容差: diff=0.02, tolerance=0.01 -> 不通过。"""
        # 100.02 = 60 + 40 -> diff = 0.02 > 0.01
        result = RuleRunner.run(make_rule(), make_ctx(100.02, 60.0, 40.0))
        assert result.passed is False
        assert result.diff == pytest.approx(0.02)

    def test_diff_just_within_tolerance_passes(self) -> None:
        """差额刚好在容差内: diff=0.005, tolerance=0.01 -> 通过。"""
        # 100.005 = 60 + 40 -> diff = 0.005 < 0.01
        result = RuleRunner.run(make_rule(), make_ctx(100.005, 60.0, 40.0))
        assert result.passed is True

    def test_zero_tolerance_exact_match_passes(self) -> None:
        """零容差 + 精确匹配 -> 通过。"""
        rule = make_rule(tolerance=0.0)
        result = RuleRunner.run(rule, make_ctx(100.0, 60.0, 40.0))
        assert result.passed is True

    def test_zero_tolerance_tiny_diff_fails(self) -> None:
        """零容差 + 任何差额 -> 不通过。"""
        rule = make_rule(tolerance=0.0)
        # 100.001 != 100.0
        result = RuleRunner.run(rule, make_ctx(100.001, 60.0, 40.0))
        assert result.passed is False


class TestBSBAL001ZeroAndNegative:
    """零值和负值测试。"""

    def test_all_zero_passes(self) -> None:
        """全零: 0 = 0 + 0 -> 通过。"""
        result = RuleRunner.run(make_rule(), make_ctx(0.0, 0.0, 0.0))
        assert result.passed is True
        assert result.diff == 0.0

    def test_all_negative_balanced_passes(self) -> None:
        """全负平衡: -100 = -60 + -40 -> 通过。"""
        result = RuleRunner.run(make_rule(), make_ctx(-100.0, -60.0, -40.0))
        assert result.passed is True

    def test_all_negative_unbalanced_fails(self) -> None:
        """全负不平衡: -100 != -60 + -35 (-95) -> 不通过。"""
        result = RuleRunner.run(make_rule(), make_ctx(-100.0, -60.0, -35.0))
        assert result.passed is False
        assert result.diff == pytest.approx(-5.0)

    def test_mixed_sign_balanced_passes(self) -> None:
        """混合符号平衡: 100 = -20 + 120 -> 通过 (如累计亏损)。"""
        result = RuleRunner.run(make_rule(), make_ctx(100.0, -20.0, 120.0))
        assert result.passed is True


class TestBSBAL001FloatPrecision:
    """浮点精度测试。"""

    def test_float_addition_within_tolerance(self) -> None:
        """0.1+0.2 浮点精度: 0.3 ≈ 0.1+0.2 (容差内通过)。"""
        # 0.1 + 0.2 = 0.30000000000000004 in float
        # 0.3 - (0.1+0.2) = -5.55e-17, within tolerance 0.01
        result = RuleRunner.run(make_rule(), make_ctx(0.3, 0.1, 0.2))
        assert result.passed is True

    def test_large_number_float_precision(self) -> None:
        """大数浮点精度: 1e10+1.0 可能丢失精度, 但整数运算精确。"""
        # 1e10 is exactly representable in float64
        result = RuleRunner.run(make_rule(), make_ctx(1e10, 6e9, 4e9))
        assert result.passed is True


class TestBSBAL001MissingData:
    """缺失数据测试。"""

    def test_missing_asset_defaults_zero_fails(self) -> None:
        """缺少 asset_total -> 预填充为 0，公式 0 != 60+40 -> 不通过。

        build_namespace 将已知科目预填充为 0，
        缺失的 asset_total 默认 0，公式求值 0 == 100 不成立。
        """
        bs = Report(
            report_type=ReportType.BALANCE_SHEET,
            period="2024-12",
            items=[
                ReportItem(key="liability_total", name="负债合计", amount=60.0),
                ReportItem(key="equity_total", name="所有者权益合计", amount=40.0),
            ],
        )
        ctx = ValidationContext(period="2024-12")
        ctx.add_report(bs)
        result = RuleRunner.run(make_rule(), ctx)
        assert result.passed is False
        assert result.left_value == 0.0

    def test_missing_liability_defaults_zero_fails(self) -> None:
        """缺少 liability_total -> 预填充为 0，公式 100 != 0+40 -> 不通过。"""
        bs = Report(
            report_type=ReportType.BALANCE_SHEET,
            period="2024-12",
            items=[
                ReportItem(key="asset_total", name="资产总计", amount=100.0),
                ReportItem(key="equity_total", name="所有者权益合计", amount=40.0),
            ],
        )
        ctx = ValidationContext(period="2024-12")
        ctx.add_report(bs)
        result = RuleRunner.run(make_rule(), ctx)
        assert result.passed is False

    def test_missing_equity_defaults_zero_fails(self) -> None:
        """缺少 equity_total -> 预填充为 0，公式 100 != 60+0 -> 不通过。"""
        bs = Report(
            report_type=ReportType.BALANCE_SHEET,
            period="2024-12",
            items=[
                ReportItem(key="asset_total", name="资产总计", amount=100.0),
                ReportItem(key="liability_total", name="负债合计", amount=60.0),
            ],
        )
        ctx = ValidationContext(period="2024-12")
        ctx.add_report(bs)
        result = RuleRunner.run(make_rule(), ctx)
        assert result.passed is False

    def test_empty_report_defaults_zero_passes(self) -> None:
        """空报表 -> 所有已知科目预填充为 0，公式 0 == 0+0 -> 通过。"""
        bs = Report(report_type=ReportType.BALANCE_SHEET, period="2024-12")
        ctx = ValidationContext(period="2024-12")
        ctx.add_report(bs)
        result = RuleRunner.run(make_rule(), ctx)
        assert result.passed is True


class TestBSBAL001DuplicateKey:
    """重复 key 测试。"""

    def test_duplicate_key_raises(self) -> None:
        """两个 asset_total -> DuplicateItemError。"""
        with pytest.raises(DuplicateItemError):
            Report(
                report_type=ReportType.BALANCE_SHEET,
                items=[
                    ReportItem(key="asset_total", name="资产总计", amount=100.0, row=5),
                    ReportItem(key="asset_total", name="资产总计", amount=200.0, row=10),
                ],
            )


class TestBSBAL001ResultFields:
    """结果字段完整性测试。"""

    def test_result_contains_all_fields(self) -> None:
        """结果包含所有必需字段。"""
        result = RuleRunner.run(make_rule(), make_ctx(100.0, 60.0, 40.0))
        assert result.rule_id == "BS-BAL-001"
        assert result.rule_name == "资产=负债+所有者权益"
        assert result.passed is True
        assert result.severity == Severity.ERROR
        assert result.left_value == 100.0
        assert result.right_value == 100.0
        assert result.diff == pytest.approx(0.0)
        assert result.tolerance == 0.01
        assert "asset_total == liability_total + equity_total" in result.formula
        assert "通过" in result.message

    def test_fail_result_message_has_details(self) -> None:
        """失败消息包含具体差额和容差信息。"""
        result = RuleRunner.run(make_rule(), make_ctx(100.0, 60.0, 35.0))
        msg = result.message
        assert "不通过" in msg
        assert "错误" in msg  # severity=ERROR -> "错误"
        assert "5.00" in msg  # diff
        assert "100.00" in msg  # left_value
        assert "95.00" in msg  # right_value (60+35)

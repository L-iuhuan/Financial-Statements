"""ToleranceComparator 的单元测试。

覆盖: 精确匹配、边界值、边界外、零值、负值、NaN、负容差、相对容差基准0。
"""

from __future__ import annotations

import pytest

from fsa.core.engine.comparator import RelativeBaseZeroError, ToleranceComparator
from fsa.core.exceptions import EvaluationError, InvalidToleranceError
from fsa.core.models.rule import ToleranceType


class TestCompareExact:
    """EXACT 容差类型测试。"""

    def test_exact_match_returns_pass(self) -> None:
        """精确匹配: diff=0。"""
        passed, diff = ToleranceComparator.compare(
            100.0, 100.0, ToleranceType.EXACT, 0.01
        )
        assert passed is True
        assert diff == 0.0

    def test_diff_within_tolerance_returns_pass(self) -> None:
        """边界内: diff=0.005 < tolerance=0.01。"""
        passed, diff = ToleranceComparator.compare(
            100.005, 100.0, ToleranceType.EXACT, 0.01
        )
        assert passed is True
        assert diff == pytest.approx(0.005)

    def test_diff_at_tolerance_returns_pass(self) -> None:
        """边界值: diff=1.0 == tolerance=1.0 (用整数避免浮点精度问题)。"""
        passed, diff = ToleranceComparator.compare(
            101.0, 100.0, ToleranceType.EXACT, 1.0
        )
        assert passed is True
        assert diff == 1.0

    def test_diff_over_tolerance_returns_fail(self) -> None:
        """边界外: diff=0.011 > tolerance=0.01。"""
        passed, diff = ToleranceComparator.compare(
            100.011, 100.0, ToleranceType.EXACT, 0.01
        )
        assert passed is False
        assert diff == pytest.approx(0.011)

    def test_negative_diff_within_tolerance_returns_pass(self) -> None:
        """负差额边界内: diff=-0.005。"""
        passed, diff = ToleranceComparator.compare(
            99.995, 100.0, ToleranceType.EXACT, 0.01
        )
        assert passed is True
        assert diff == pytest.approx(-0.005)

    def test_negative_diff_over_tolerance_returns_fail(self) -> None:
        """负差额边界外: diff=-0.011。"""
        passed, diff = ToleranceComparator.compare(
            99.989, 100.0, ToleranceType.EXACT, 0.01
        )
        assert passed is False
        assert diff == pytest.approx(-0.011)

    def test_zero_tolerance_exact_match_passes(self) -> None:
        """零容差: 精确匹配通过。"""
        passed, diff = ToleranceComparator.compare(
            100.0, 100.0, ToleranceType.EXACT, 0.0
        )
        assert passed is True
        assert diff == 0.0

    def test_zero_tolerance_tiny_diff_fails(self) -> None:
        """零容差: 任何差额都失败。"""
        passed, diff = ToleranceComparator.compare(
            100.001, 100.0, ToleranceType.EXACT, 0.0
        )
        assert passed is False
        assert diff == pytest.approx(0.001)

    def test_both_zero_returns_pass(self) -> None:
        """零值: 双方为0。"""
        passed, diff = ToleranceComparator.compare(
            0.0, 0.0, ToleranceType.EXACT, 0.01
        )
        assert passed is True
        assert diff == 0.0

    def test_both_negative_returns_pass(self) -> None:
        """负值: 双方为负且相等。"""
        passed, diff = ToleranceComparator.compare(
            -100.0, -100.0, ToleranceType.EXACT, 0.01
        )
        assert passed is True
        assert diff == 0.0

    def test_both_negative_unbalanced_fails(self) -> None:
        """负值: 双方为负且不等。"""
        passed, diff = ToleranceComparator.compare(
            -100.0, -95.0, ToleranceType.EXACT, 0.01
        )
        assert passed is False
        assert diff == pytest.approx(-5.0)

    def test_large_numbers_pass(self) -> None:
        """大数: 1e15级别。"""
        passed, diff = ToleranceComparator.compare(
            1e15, 1e15, ToleranceType.EXACT, 0.01
        )
        assert passed is True
        assert diff == 0.0

    def test_large_numbers_tiny_diff_fails(self) -> None:
        """大数: 1e15级别的1.0差额 (超出容差0.01)。

        注意: float64在1e15量级的ULP约为0.125，
        因此 1e15+0.1 实际存储为 1e15+0.125。
        这里用 1.0 差额确保可精确表示。
        """
        passed, diff = ToleranceComparator.compare(
            1e15 + 1.0, 1e15, ToleranceType.EXACT, 0.01
        )
        assert passed is False
        assert diff == pytest.approx(1.0)

    def test_float_precision_within_tolerance(self) -> None:
        """浮点精度: 0.1+0.2=0.30000000000000004, 容差内通过。"""
        left = 0.1 + 0.2  # 0.30000000000000004
        right = 0.3
        passed, diff = ToleranceComparator.compare(
            left, right, ToleranceType.EXACT, 0.01
        )
        assert passed is True
        assert abs(diff) < 0.01

    def test_nan_value_raises(self) -> None:
        """NaN: 抛 ValueError。"""
        with pytest.raises(ValueError, match="NaN"):
            ToleranceComparator.compare(
                float("nan"), 100.0, ToleranceType.EXACT, 0.01
            )

    def test_inf_value_raises(self) -> None:
        """无穷大: 抛中文 ValueError。"""
        with pytest.raises(ValueError, match="无穷大"):
            ToleranceComparator.compare(
                float("inf"), 100.0, ToleranceType.EXACT, 0.01
            )
        with pytest.raises(ValueError, match="无穷大"):
            ToleranceComparator.compare(
                100.0, float("-inf"), ToleranceType.EXACT, 0.01
            )

    def test_negative_tolerance_raises(self) -> None:
        """负容差: 抛 InvalidToleranceError。"""
        with pytest.raises(InvalidToleranceError):
            ToleranceComparator.compare(
                100.0, 100.0, ToleranceType.EXACT, -0.01
            )


class TestCompareAbsolute:
    """ABSOLUTE 容差类型测试 (与 EXACT 算法相同)。"""

    def test_absolute_same_as_exact(self) -> None:
        """ABSOLUTE 与 EXACT 行为一致。"""
        for left, right in [(100.0, 100.0), (100.01, 100.0), (99.99, 100.0)]:
            passed_exact, diff_exact = ToleranceComparator.compare(
                left, right, ToleranceType.EXACT, 0.01
            )
            passed_abs, diff_abs = ToleranceComparator.compare(
                left, right, ToleranceType.ABSOLUTE, 0.01
            )
            assert passed_exact == passed_abs
            assert diff_exact == diff_abs


class TestCompareRelative:
    """RELATIVE 容差类型测试。"""

    def test_relative_within_tolerance(self) -> None:
        """相对差异在容差内: diff/|right| = 0.01/100 = 0.0001 <= 0.30。"""
        passed, diff = ToleranceComparator.compare(
            101.0, 100.0, ToleranceType.RELATIVE, 0.30
        )
        assert passed is True
        assert diff == pytest.approx(1.0)

    def test_relative_over_tolerance(self) -> None:
        """相对差异超出容差: diff/|right| = 50/100 = 0.50 > 0.30。"""
        passed, diff = ToleranceComparator.compare(
            150.0, 100.0, ToleranceType.RELATIVE, 0.30
        )
        assert passed is False
        assert diff == pytest.approx(50.0)

    def test_relative_at_tolerance_boundary(self) -> None:
        """边界值: diff/|right| = 30/100 = 0.30 == tolerance=0.30。"""
        passed, diff = ToleranceComparator.compare(
            130.0, 100.0, ToleranceType.RELATIVE, 0.30
        )
        assert passed is True

    def test_relative_both_zero_returns_pass(self) -> None:
        """双方都为0时通过。"""
        passed, diff = ToleranceComparator.compare(
            0.0, 0.0, ToleranceType.RELATIVE, 0.30
        )
        assert passed is True
        assert diff == 0.0

    def test_relative_right_zero_left_nonzero_raises(self) -> None:
        """基准值为0但左值非0时抛专用异常（中文财务文案）。"""
        with pytest.raises(
            RelativeBaseZeroError,
            match="基准科目金额为 0，无法计算相对差异，本规则跳过校验",
        ):
            ToleranceComparator.compare(
                100.0, 0.0, ToleranceType.RELATIVE, 0.30
            )

    def test_relative_right_zero_left_nonzero_message(self) -> None:
        """异常消息为面向财务用户的中文，不含技术术语。"""
        with pytest.raises(RelativeBaseZeroError) as excinfo:
            ToleranceComparator.compare(
                100.0, 0.0, ToleranceType.RELATIVE, 0.30
            )
        assert "基准科目金额为 0" in str(excinfo.value)
        assert "跳过校验" in str(excinfo.value)
        assert "right" not in str(excinfo.value)

    def test_relative_base_zero_error_is_evaluation_error(self) -> None:
        """专用异常继承 EvaluationError，服务层将其归入跳过路径 (P1)。"""
        assert issubclass(RelativeBaseZeroError, EvaluationError)

    def test_relative_negative_values(self) -> None:
        """负值: 相对差异基于绝对值。"""
        passed, diff = ToleranceComparator.compare(
            -130.0, -100.0, ToleranceType.RELATIVE, 0.30
        )
        assert passed is True


class TestPrecisionWarning:
    """大额比较时精度边界提示（不改变判断结果）。"""

    def test_large_magnitude_logs_warning(self) -> None:
        """|值| > 1e14 时 logger.warning 提示精度边界。"""
        import io

        from loguru import logger

        sink = io.StringIO()
        sink_id = logger.add(sink, level="WARNING")
        try:
            ToleranceComparator.compare(1e15, 1e15, ToleranceType.EXACT, 0.01)
        finally:
            logger.remove(sink_id)
        assert "精度边界" in sink.getvalue()

    def test_large_magnitude_does_not_change_result(self) -> None:
        """精度提示不改变判断结果：大额仍正确通过。"""
        passed, diff = ToleranceComparator.compare(
            1e15, 1e15, ToleranceType.EXACT, 0.01
        )
        assert passed is True
        assert diff == 0.0

    def test_small_magnitude_no_warning(self) -> None:
        """|值| <= 1e14 时不触发精度提示。"""
        import io

        from loguru import logger

        sink = io.StringIO()
        sink_id = logger.add(sink, level="WARNING")
        try:
            ToleranceComparator.compare(100.0, 100.0, ToleranceType.EXACT, 0.01)
        finally:
            logger.remove(sink_id)
        assert "精度边界" not in sink.getvalue()

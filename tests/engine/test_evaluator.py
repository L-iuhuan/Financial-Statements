"""ExpressionEvaluator 的单元测试。

覆盖: 公式拆分、简单算术、变量求值、缺失变量、除零、语法错误、空表达式。
"""

from __future__ import annotations

import pytest

from fsa.core.engine.evaluator import ExpressionEvaluator
from fsa.core.exceptions import EvaluationError, FormulaParseError


class TestSplitFormula:
    """split_formula 测试。"""

    def test_normal_split(self) -> None:
        """正常拆分: 'a == b + c' -> ('a', 'b + c')。"""
        left, right = ExpressionEvaluator.split_formula("a == b + c")
        assert left == "a"
        assert right == "b + c"

    def test_split_with_spaces(self) -> None:
        """带空格: '  a  ==  b  ' -> ('a', 'b')。"""
        left, right = ExpressionEvaluator.split_formula("  a  ==  b  ")
        assert left == "a"
        assert right == "b"

    def test_complex_formula_split(self) -> None:
        """复杂公式: BS-BAL-004 公式。"""
        formula = "paid_in_capital + capital_reserve + surplus_reserve == equity_total"
        left, right = ExpressionEvaluator.split_formula(formula)
        assert left == "paid_in_capital + capital_reserve + surplus_reserve"
        assert right == "equity_total"

    def test_no_equals_raises(self) -> None:
        """无 ==: 抛 FormulaParseError。"""
        with pytest.raises(FormulaParseError, match="必须包含"):
            ExpressionEvaluator.split_formula("a + b")

    def test_multiple_equals_raises(self) -> None:
        """多个 ==: 抛 FormulaParseError。"""
        with pytest.raises(FormulaParseError, match="2 个"):
            ExpressionEvaluator.split_formula("a == b == c")

    def test_empty_left_raises(self) -> None:
        """空左侧: '== b' 抛 FormulaParseError。"""
        with pytest.raises(FormulaParseError, match="不能为空"):
            ExpressionEvaluator.split_formula("== b")

    def test_empty_right_raises(self) -> None:
        """空右侧: 'a ==' 抛 FormulaParseError。"""
        with pytest.raises(FormulaParseError, match="不能为空"):
            ExpressionEvaluator.split_formula("a ==")


class TestEvaluate:
    """evaluate 测试。"""

    def test_simple_number(self) -> None:
        """纯数字: '100' -> 100.0。"""
        assert ExpressionEvaluator.evaluate("100", {}) == 100.0

    def test_addition(self) -> None:
        """加法: '60 + 40' -> 100.0。"""
        assert ExpressionEvaluator.evaluate("60 + 40", {}) == 100.0

    def test_subtraction(self) -> None:
        """减法: '100 - 40' -> 60.0。"""
        assert ExpressionEvaluator.evaluate("100 - 40", {}) == 60.0

    def test_multiplication(self) -> None:
        """乘法: '60 * 2' -> 120.0。"""
        assert ExpressionEvaluator.evaluate("60 * 2", {}) == 120.0

    def test_division(self) -> None:
        """除法: '100 / 4' -> 25.0。"""
        assert ExpressionEvaluator.evaluate("100 / 4", {}) == 25.0

    def test_parentheses(self) -> None:
        """括号: '(60 + 40) * 2' -> 200.0。"""
        assert ExpressionEvaluator.evaluate("(60 + 40) * 2", {}) == 200.0

    def test_negative_number(self) -> None:
        """负数: '-100' -> -100.0。"""
        assert ExpressionEvaluator.evaluate("-100", {}) == -100.0

    def test_with_variables(self) -> None:
        """变量: 'a + b' with a=60, b=40 -> 100.0。"""
        result = ExpressionEvaluator.evaluate("a + b", {"a": 60.0, "b": 40.0})
        assert result == 100.0

    def test_complex_with_variables(self) -> None:
        """复杂变量: 'a - (b + c)' with a=100, b=60, c=40 -> 0.0。"""
        result = ExpressionEvaluator.evaluate(
            "a - (b + c)", {"a": 100.0, "b": 60.0, "c": 40.0}
        )
        assert result == 0.0

    def test_bs_bal_001_formula(self) -> None:
        """BS-BAL-001 右侧: 'liability_total + equity_total' -> 100.0。"""
        ns = {"liability_total": 60.0, "equity_total": 40.0}
        assert ExpressionEvaluator.evaluate("liability_total + equity_total", ns) == 100.0

    def test_missing_variable_raises(self) -> None:
        """缺失变量: 抛 EvaluationError。"""
        with pytest.raises(EvaluationError, match="未定义"):
            ExpressionEvaluator.evaluate("a + b", {"a": 60.0})

    def test_division_by_zero_raises(self) -> None:
        """除零: 抛 EvaluationError。"""
        with pytest.raises(EvaluationError, match="除零"):
            ExpressionEvaluator.evaluate("100 / 0", {})

    def test_syntax_error_raises(self) -> None:
        """语法错误: 'a +* b' 抛 FormulaParseError 或 EvaluationError。"""
        with pytest.raises((FormulaParseError, EvaluationError)):
            ExpressionEvaluator.evaluate("a +* b", {"a": 1.0, "b": 2.0})

    def test_empty_expression_raises(self) -> None:
        """空表达式: 抛异常。"""
        with pytest.raises((FormulaParseError, EvaluationError)):
            ExpressionEvaluator.evaluate("", {})

    def test_negative_values(self) -> None:
        """负值变量: 'a + b' with a=-60, b=-40 -> -100.0。"""
        result = ExpressionEvaluator.evaluate("a + b", {"a": -60.0, "b": -40.0})
        assert result == -100.0

    def test_zero_values(self) -> None:
        """零值变量: 'a + b' with a=0, b=0 -> 0.0。"""
        result = ExpressionEvaluator.evaluate("a + b", {"a": 0.0, "b": 0.0})
        assert result == 0.0

    def test_large_values(self) -> None:
        """大数: 'a + b' with a=6e14, b=4e14 -> 1e15。"""
        result = ExpressionEvaluator.evaluate("a + b", {"a": 6e14, "b": 4e14})
        assert result == 1e15

    def test_float_precision(self) -> None:
        """浮点精度: 0.1+0.2 在容差内接近0.3。"""
        result = ExpressionEvaluator.evaluate("a + b", {"a": 0.1, "b": 0.2})
        assert abs(result - 0.3) < 0.001

    def test_result_is_float(self) -> None:
        """返回值类型: 总是 float。"""
        result = ExpressionEvaluator.evaluate("100", {})
        assert isinstance(result, float)

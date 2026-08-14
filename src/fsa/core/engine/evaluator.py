"""表达式求值器: 拆分公式并求值左右两侧。

使用 simpleeval 库进行安全的表达式求值（AST 白名单，非 eval()）。
公式 "a == b + c" 被拆分为:
  left = "a", right = "b + c"
然后分别求值。
"""

from __future__ import annotations

from simpleeval import InvalidExpression, NameNotDefined, simple_eval

from fsa.core.exceptions import EvaluationError, FormulaParseError

# simpleeval 默认不提供任何内置函数，需要手动注入常用的数学函数
_EVAL_FUNCTIONS: dict[str, object] = {
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
    "sum": sum,
}


class ExpressionEvaluator:
    """表达式求值器。"""

    @staticmethod
    def split_formula(formula: str) -> tuple[str, str]:
        """将公式按 '==' 拆分为左右两侧表达式。

        Args:
            formula: 公式字符串，如 "asset_total == liability_total + equity_total"

        Returns:
            (left_expr, right_expr) 元组

        Raises:
            FormulaParseError: 公式不含 ==, 或含多个 ==
        """
        if "==" not in formula:
            raise FormulaParseError(formula, "公式必须包含 '==' 进行相等校验")

        parts = formula.split("==")
        if len(parts) != 2:
            raise FormulaParseError(
                formula, f"公式包含 {len(parts) - 1} 个 '=='，应为 1 个"
            )

        left = parts[0].strip()
        right = parts[1].strip()

        if not left or not right:
            raise FormulaParseError(formula, "'==' 两侧表达式不能为空")

        return left, right

    @staticmethod
    def _safe_eval(expression: str, namespace: dict[str, float]) -> bool | float:
        """用 simpleeval 求值表达式并统一异常映射。

        两个公开方法 (evaluate / evaluate_boolean) 共用此私有方法，
        调用后各自做数值/布尔类型转换。

        Args:
            expression: 表达式字符串
            namespace: 变量命名空间

        Returns:
            求值结果（数值或布尔）

        Raises:
            EvaluationError: 变量未定义、除零、类型错误、结果为 None 等
            FormulaParseError: 语法错误
        """
        try:
            result = simple_eval(expression, names=namespace, functions=_EVAL_FUNCTIONS)
        except NameNotDefined as e:
            raise EvaluationError(
                expression,
                f"变量「{e.name}」未定义。请检查报表中是否包含该项目。",
            ) from e
        except ZeroDivisionError as e:
            raise EvaluationError(
                expression, "除零错误。公式中存在除以零的操作。"
            ) from e
        except (SyntaxError, InvalidExpression) as e:
            raise FormulaParseError(expression, f"语法错误: {e}") from e
        except TypeError as e:
            raise EvaluationError(expression, f"类型错误: {e}") from e

        if result is None:
            raise EvaluationError(expression, "表达式求值结果为 None")

        if isinstance(result, bool):
            return result
        return float(result)

    @staticmethod
    def evaluate(expression: str, namespace: dict[str, float]) -> float:
        """用 simpleeval 求值表达式。

        Args:
            expression: 表达式字符串，如 "liability_total + equity_total"
            namespace: 变量命名空间，如 {"liability_total": 60.0, "equity_total": 40.0}

        Returns:
            求值结果 (float)

        Raises:
            EvaluationError: 变量未定义、除零、类型错误等
            FormulaParseError: 语法错误
        """
        return float(ExpressionEvaluator._safe_eval(expression, namespace))

    @staticmethod
    def evaluate_boolean(expression: str, namespace: dict[str, float]) -> bool:
        """求值阈值/范围判断表达式，返回布尔结果。

        用于不含 '==' 的公式，如:
        - "liability_total / asset_total <= 0.85"
        - "net_profit <= 0 or operating_net >= 0"
        - "0 <= (revenue - operating_cost)/revenue <= 1"

        Args:
            expression: 判断表达式字符串
            namespace: 变量命名空间

        Returns:
            True 表示条件满足（校验通过），False 表示不满足

        Raises:
            EvaluationError: 变量未定义、除零、类型错误等
            FormulaParseError: 语法错误
        """
        return bool(ExpressionEvaluator._safe_eval(expression, namespace))

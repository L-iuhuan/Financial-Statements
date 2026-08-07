"""规则执行器: 接收规则和上下文，执行校验，返回结果。

RuleRunner 是规则引擎的入口点:
1. 从上下文构建变量命名空间
2. 拆分公式为左右两侧
3. 分别求值
4. 用容差比较器判断是否通过
5. 构建 ValidationResult
"""

from __future__ import annotations

from loguru import logger

from fsa.core.engine.comparator import ToleranceComparator
from fsa.core.engine.evaluator import ExpressionEvaluator
from fsa.core.exceptions import MissingItemError
from fsa.core.models.result import ValidationContext, ValidationResult
from fsa.core.models.rule import ReconciliationRule, Severity


class RuleRunner:
    """规则执行器。执行单条规则，返回校验结果。"""

    @staticmethod
    def run(rule: ReconciliationRule, context: ValidationContext) -> ValidationResult:
        """执行一条校验规则。

        Args:
            rule: 勾稽校验规则
            context: 校验上下文 (包含报表数据)

        Returns:
            ValidationResult 校验结果

        Raises:
            MissingItemError: 报表中缺少规则所需的变量
            FormulaParseError: 公式解析失败
            EvaluationError: 表达式求值失败
        """
        logger.info(f"执行规则: {rule.rule_id} {rule.name}")

        namespace = context.build_namespace(rule.statements)

        left_expr, right_expr = ExpressionEvaluator.split_formula(rule.formula)

        left_value = ExpressionEvaluator.evaluate(left_expr, namespace)
        right_value = ExpressionEvaluator.evaluate(right_expr, namespace)

        passed, diff = ToleranceComparator.compare(
            left_value, right_value, rule.tolerance_type, rule.tolerance
        )

        message = RuleRunner._build_message(rule, passed, left_value, right_value, diff)

        logger.info(
            f"规则 {rule.rule_id} 结果: {'通过' if passed else '不通过'}, "
            f"左值={left_value}, 右值={right_value}, 差额={diff}"
        )

        return ValidationResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            passed=passed,
            severity=rule.severity,
            left_value=left_value,
            right_value=right_value,
            diff=diff,
            tolerance=rule.tolerance,
            formula=rule.formula,
            message=message,
        )

    @staticmethod
    def _build_message(
        rule: ReconciliationRule,
        passed: bool,
        left: float,
        right: float,
        diff: float,
    ) -> str:
        """构建面向财务用户的中文消息。"""
        if passed:
            return f"{rule.name}: 校验通过（差额 {diff:.2f} 元，容差内）"

        severity_text = {
            Severity.ERROR: "错误",
            Severity.WARNING: "警告",
            Severity.INFO: "提示",
        }.get(rule.severity, "异常")

        return (
            f"{rule.name}: 校验不通过 [{severity_text}]\n"
            f"  左侧值: {left:,.2f} 元\n"
            f"  右侧值: {right:,.2f} 元\n"
            f"  差额: {diff:,.2f} 元 (超出容差 {rule.tolerance:.2f} 元)"
        )

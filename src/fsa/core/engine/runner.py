"""规则执行器: 接收规则和上下文，执行校验，返回结果。

RuleRunner 是规则引擎的入口点:
1. 从上下文构建变量命名空间
2. 拆分公式为左右两侧
3. 分别求值
4. 用容差比较器判断是否通过
5. 构建 ValidationResult（含 trace 追踪）
"""

from __future__ import annotations

import re

from loguru import logger

from fsa.core.engine.comparator import ToleranceComparator
from fsa.core.engine.evaluator import ExpressionEvaluator
from fsa.core.engine.thresholds import DEFAULT_THRESHOLDS
from fsa.core.models.result import TraceItem, ValidationContext, ValidationResult
from fsa.core.models.rule import ReconciliationRule, Severity

# 公式中的函数名，在变量名提取时跳过
_FUNCTION_NAMES = frozenset({"abs", "min", "max", "round", "sum"})


class RuleRunner:
    """规则执行器。执行单条规则，返回校验结果。"""

    @staticmethod
    def run(
        rule: ReconciliationRule,
        context: ValidationContext,
        threshold_vars: dict[str, float] | None = None,
    ) -> ValidationResult:
        """执行一条校验规则。

        支持两种公式类型:
        - 等式公式 (含 '=='): 拆分左右两侧，分别求值，用容差比较
        - 阈值公式 (含 <=, >=, <, >): 整体求值为布尔结果

        行业阈值: 规则库中 LR-* 阈值规则使用阈值变量(如 dar_threshold)，
        求值前注入阈值变量值。未提供 threshold_vars 时使用 general 默认值，
        与替换前的魔法数字行为完全一致 (回归不破, P2 确定性)。

        Args:
            rule: 勾稽校验规则
            context: 校验上下文 (包含报表数据)
            threshold_vars: 阈值变量 -> 值 (按行业配置, 见 entity_config)。

        Returns:
            ValidationResult 校验结果

        Raises:
            MissingItemError: 报表中缺少规则所需的变量
            FormulaParseError: 公式解析失败
            EvaluationError: 表达式求值失败
        """
        logger.info(f"执行规则: {rule.rule_id} {rule.name}")

        namespace = context.build_namespace(rule.statements)
        merged = RuleRunner._merged_thresholds(threshold_vars)
        namespace.update(merged)

        if "==" in rule.formula:
            return RuleRunner._run_equality(rule, namespace, context, merged)
        else:
            return RuleRunner._run_threshold(rule, namespace, context, merged)

    @staticmethod
    def _merged_thresholds(
        threshold_vars: dict[str, float] | None,
    ) -> dict[str, float]:
        """合并阈值变量: 未指定项回落 general 默认值, 保证确定性。"""
        merged = dict(DEFAULT_THRESHOLDS)
        if threshold_vars:
            merged.update(threshold_vars)
        return merged

    @staticmethod
    def _run_equality(
        rule: ReconciliationRule,
        namespace: dict[str, float],
        context: ValidationContext,
        threshold_vars: dict[str, float],
    ) -> ValidationResult:
        """执行等式公式 (含 ==)。"""
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

        trace = RuleRunner._build_trace_equality(
            left_expr, right_expr, context, threshold_vars
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
            category=rule.category,
            trace=trace,
        )

    @staticmethod
    def _run_threshold(
        rule: ReconciliationRule,
        namespace: dict[str, float],
        context: ValidationContext,
        threshold_vars: dict[str, float],
    ) -> ValidationResult:
        """执行阈值公式 (含 <=, >=, <, >, and, or)。"""
        passed = ExpressionEvaluator.evaluate_boolean(rule.formula, namespace)

        message = RuleRunner._build_threshold_message(rule, passed, threshold_vars)

        logger.info(
            f"规则 {rule.rule_id} 结果: {'通过' if passed else '不通过'} (阈值判断)"
        )

        trace = RuleRunner._build_trace_formula(rule.formula, context, threshold_vars)

        return ValidationResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            passed=passed,
            severity=rule.severity,
            left_value=0.0,
            right_value=0.0,
            diff=0.0,
            tolerance=rule.tolerance,
            formula=rule.formula,
            message=message,
            category=rule.category,
            trace=trace,
        )

    @staticmethod
    def _build_trace_equality(
        left_expr: str,
        right_expr: str,
        context: ValidationContext,
        threshold_vars: dict[str, float] | None = None,
    ) -> list[TraceItem]:
        """为等式公式构建 trace: 左侧变量 side='left'，右侧变量 side='right'。"""
        trace: list[TraceItem] = []
        seen: set[str] = set()

        left_vars = _extract_variable_names(left_expr)
        right_vars = _extract_variable_names(right_expr)

        for var in left_vars:
            _add_trace_item(trace, seen, var, "left", context, threshold_vars)
        for var in right_vars:
            _add_trace_item(trace, seen, var, "right", context, threshold_vars)

        return trace

    @staticmethod
    def _build_trace_formula(
        formula: str,
        context: ValidationContext,
        threshold_vars: dict[str, float] | None = None,
    ) -> list[TraceItem]:
        """为阈值公式构建 trace: 所有变量 side='left'。"""
        trace: list[TraceItem] = []
        seen: set[str] = set()

        vars_set = _extract_variable_names(formula)
        for var in vars_set:
            _add_trace_item(trace, seen, var, "left", context, threshold_vars)

        return trace

    @staticmethod
    def _build_threshold_message(
        rule: ReconciliationRule,
        passed: bool,
        threshold_vars: dict[str, float] | None = None,
    ) -> str:
        """构建阈值判断的中文消息 (阈值变量替换为实际值便于用户理解)。"""
        if passed:
            return f"{rule.name}: 校验通过（满足阈值条件）"

        severity_text = {
            Severity.ERROR: "错误",
            Severity.WARNING: "警告",
            Severity.INFO: "提示",
        }.get(rule.severity, "异常")

        return (
            f"{rule.name}: 校验不通过 [{severity_text}]\n"
            f"  判断条件: {_display_formula(rule.formula, threshold_vars)}"
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


def _extract_variable_names(expression: str) -> list[str]:
    """从表达式中提取变量名（标识符 tokens）。

    过滤掉函数名和运算符。

    Args:
        expression: 表达式字符串

    Returns:
        变量名列表（按出现顺序，去重）
    """
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expression)
    seen: set[str] = set()
    result: list[str] = []
    for token in tokens:
        if token in _FUNCTION_NAMES:
            continue
        if token in ("and", "or", "not"):
            continue
        if token not in seen:
            seen.add(token)
            result.append(token)
    return result


def _display_formula(
    formula: str, threshold_vars: dict[str, float] | None
) -> str:
    """将公式中的阈值变量名替换为实际值，便于财务用户理解判断条件。

    变量名按长度降序替换，避免长名包含短名时被部分替换。
    """
    if not threshold_vars:
        return formula
    display = formula
    for var in sorted(threshold_vars, key=len, reverse=True):
        display = display.replace(var, _format_threshold(threshold_vars[var]))
    return display


def _format_threshold(value: float) -> str:
    """格式化阈值数字: 1.0 -> '1', 0.85 -> '0.85', 0.8 -> '0.8'。"""
    if value == int(value):
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _add_trace_item(
    trace: list[TraceItem],
    seen: set[str],
    key: str,
    side: str,
    context: ValidationContext,
    extra_values: dict[str, float] | None = None,
) -> None:
    """查找变量并添加到 trace 列表。

    Args:
        trace: 目标 trace 列表
        seen: 已处理变量集合
        key: 变量名
        side: 公式侧 "left" 或 "right"
        context: 校验上下文
        extra_values: 额外注入的变量值 (如行业阈值), 用于 trace 展示实际取值
    """
    if key in seen:
        return
    seen.add(key)

    # 处理双金额列后缀: {key}_ending 用期末值, {key}_beginning 用期初值
    lookup_key = key
    use_beginning = False
    if key.endswith("_ending"):
        lookup_key = key[: -len("_ending")]
    elif key.endswith("_beginning"):
        lookup_key = key[: -len("_beginning")]
        use_beginning = True

    item = context.get_item(lookup_key)
    if item is not None:
        amount = item.amount
        if use_beginning:
            amount = item.beginning_amount if item.beginning_amount is not None else 0.0
        trace.append(
            TraceItem(
                key=key,
                name=item.name,
                amount=amount,
                row=item.row,
                column=item.column,
                side=side,
            )
        )
    elif extra_values is not None and key in extra_values:
        # 阈值变量 (由 runner 注入): 展示实际注入值便于审计追溯 (P3)
        trace.append(
            TraceItem(
                key=key,
                name=key,
                amount=float(extra_values[key]),
                row=0,
                column="",
                side=side,
            )
        )
    else:
        # 变量在报表中未找到（来自 KNOWN_LINE_ITEM_KEYS 预填充 0）。
        # column 用中文说明标注，便于财务用户理解该值为按 0 处理而非取自报表。
        trace.append(
            TraceItem(
                key=key,
                name=key,
                amount=0.0,
                row=0,
                column="未在报表中找到（按 0 处理）",
                side=side,
            )
        )

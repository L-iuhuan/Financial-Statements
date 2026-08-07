"""财务报表校验系统异常层次结构。

所有自定义异常继承自 FSAError。错误信息用中文，面向财务用户。
"""

from __future__ import annotations


class FSAError(Exception):
    """财务报表校验系统根异常。所有自定义异常的基类。"""


class MissingItemError(FSAError):
    """报表中缺少规则所需的项目。

    在规则求值时，某个变量（如 asset_total）在报表中找不到对应的 ReportItem。
    """

    def __init__(self, key: str, report_type: str, rule_id: str) -> None:
        self.key = key
        self.report_type = report_type
        self.rule_id = rule_id
        super().__init__(
            f"规则 {rule_id} 需要项目「{key}」，但在{report_type}中未找到。"
            f"请检查报表是否包含该项目，或科目映射是否正确。"
        )


class DuplicateItemError(FSAError):
    """报表中存在重复项目（同一 key 出现多次）。"""

    def __init__(self, key: str, report_type: str) -> None:
        self.key = key
        self.report_type = report_type
        super().__init__(
            f"{report_type}中存在重复的项目「{key}」。"
            f"请检查报表数据，确保每个项目只出现一次。"
        )


class FormulaParseError(FSAError):
    """公式解析失败（语法错误、缺少==等）。"""

    def __init__(self, formula: str, reason: str) -> None:
        self.formula = formula
        self.reason = reason
        super().__init__(f"公式解析失败: 「{formula}」({reason})")


class EvaluationError(FSAError):
    """表达式求值失败（变量未定义、除零等）。"""

    def __init__(self, expression: str, reason: str) -> None:
        self.expression = expression
        self.reason = reason
        super().__init__(f"表达式求值失败: 「{expression}」({reason})")


class InvalidToleranceError(FSAError):
    """容差参数无效（负数、NaN等）。"""

    def __init__(self, tolerance: float) -> None:
        self.tolerance = tolerance
        super().__init__(f"容差参数无效: {tolerance}。容差必须 >= 0。")

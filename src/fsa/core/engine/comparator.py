"""容差比较器: 根据容差类型和容差值，判断校验是否通过。

支持四种容差类型:
- EXACT: |left - right| <= tolerance (绝对差异)
- ABSOLUTE: 同 EXACT (语义不同，算法相同)
- RELATIVE: |left - right| / |right| <= tolerance (相对差异)
- THRESHOLD: 值与阈值比较 (V1实现)
"""

from __future__ import annotations

import math

from loguru import logger

from fsa.core.exceptions import EvaluationError, InvalidToleranceError
from fsa.core.models.rule import ToleranceType

# 金额超过该量级时 float 尾数精度开始受限（1e14 附近 ULP ≈ 0.016），
# 触发仅提示不改变判断结果（P2 确定性）。
_PRECISION_WARN_MAGNITUDE: float = 1e14


class RelativeBaseZeroError(EvaluationError):
    """相对容差比较时基准值（右值）为 0 且左值非 0。

    属于"数据不足"而非"执行错误"：按 P1（宁可漏报不可误报）原则，
    此类场景应跳过校验而非计为执行异常。继承 EvaluationError，
    使 ValidationService 将其与"缺少变量"归入同一跳过路径。
    """

    def __init__(self) -> None:
        # 不套用 EvaluationError 的"表达式求值失败"前缀，
        # 直接保留面向财务用户的中文消息 (P4/P6)。
        Exception.__init__(self, "基准科目金额为 0，无法计算相对差异，本规则跳过校验")


class ToleranceComparator:
    """容差比较器。根据容差类型执行不同的比较逻辑。"""

    @staticmethod
    def compare(
        left: float,
        right: float,
        tolerance_type: ToleranceType,
        tolerance: float,
    ) -> tuple[bool, float]:
        """比较两个值是否在容差范围内。

        Args:
            left: 公式左侧计算值
            right: 公式右侧计算值
            tolerance_type: 容差类型
            tolerance: 容差值

        Returns:
            (passed, diff) 元组:
            - passed: 是否通过
            - diff: 差额 = left - right

        Raises:
            InvalidToleranceError: 容差为负数
            ValueError: 值为 NaN，或未知的容差类型
            RelativeBaseZeroError: 相对容差基准值为 0 且左值非 0
        """
        if tolerance < 0:
            raise InvalidToleranceError(tolerance)
        if math.isnan(left) or math.isnan(right):
            raise ValueError(f"比较值包含 NaN: left={left}, right={right}")

        if abs(left) > _PRECISION_WARN_MAGNITUDE or abs(right) > _PRECISION_WARN_MAGNITUDE:
            logger.warning(
                f"容差比较金额超过精度边界 (|左值|={abs(left):.2f}, "
                f"|右值|={abs(right):.2f})，float 尾数精度有限，结果请结合业务复核"
            )

        diff = left - right

        if tolerance_type in (ToleranceType.EXACT, ToleranceType.ABSOLUTE):
            return abs(diff) <= tolerance, diff

        if tolerance_type == ToleranceType.RELATIVE:
            if right == 0:
                if left == 0:
                    return True, 0.0
                raise RelativeBaseZeroError()
            relative_diff = abs(diff) / abs(right)
            return relative_diff <= tolerance, diff

        if tolerance_type == ToleranceType.THRESHOLD:
            return abs(diff) <= tolerance, diff

        # 理论上不会到达 (枚举已穷尽)
        raise ValueError(f"未知的容差类型: {tolerance_type}")

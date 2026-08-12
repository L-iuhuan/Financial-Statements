"""容差比较器: 根据容差类型和容差值，判断校验是否通过。

支持四种容差类型:
- EXACT: |left - right| <= tolerance (绝对差异)
- ABSOLUTE: 同 EXACT (语义不同，算法相同)
- RELATIVE: |left - right| / |right| <= tolerance (相对差异)
- THRESHOLD: 值与阈值比较 (V1实现)
"""

from __future__ import annotations

import math

from fsa.core.exceptions import InvalidToleranceError
from fsa.core.models.rule import ToleranceType


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
            ValueError: 值为 NaN，或相对容差基准为0
        """
        if tolerance < 0:
            raise InvalidToleranceError(tolerance)
        if math.isnan(left) or math.isnan(right):
            raise ValueError(f"比较值包含 NaN: left={left}, right={right}")

        diff = left - right

        if tolerance_type in (ToleranceType.EXACT, ToleranceType.ABSOLUTE):
            return abs(diff) <= tolerance, diff

        if tolerance_type == ToleranceType.RELATIVE:
            if right == 0:
                if left == 0:
                    return True, 0.0
                raise ValueError(
                    "相对容差比较失败: 基准值(right)为0，无法计算相对差异"
                )
            relative_diff = abs(diff) / abs(right)
            return relative_diff <= tolerance, diff

        if tolerance_type == ToleranceType.THRESHOLD:
            return abs(diff) <= tolerance, diff

        # 理论上不会到达 (枚举已穷尽)
        raise ValueError(f"未知的容差类型: {tolerance_type}")

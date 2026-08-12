"""验证诊断引擎: 构建假失败结果, 运行诊断, 验证输出为中文且包含关键部分。

用法: python scripts/verify_diagnosis.py
"""

from __future__ import annotations

import io
import sys

from fsa.agent.diagnosis import DiagnosisEngine
from fsa.core.models.result import TraceItem, ValidationResult
from fsa.core.models.rule import Severity

_MESSAGE = "差额超出容差"


def _make_trace() -> list[TraceItem]:
    return [
        TraceItem(
            key="asset_total", name="资产总计", amount=1234567.89,
            row=35, column="期末余额", side="left",
        ),
        TraceItem(
            key="liability_total", name="负债合计", amount=800000.00,
            row=20, column="期末余额", side="right",
        ),
        TraceItem(
            key="equity_total", name="所有者权益合计", amount=434567.89,
            row=30, column="期末余额", side="right",
        ),
    ]


def main() -> None:
    # Windows 控制台默认 GBK, 强制 UTF-8
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    result = ValidationResult(
        rule_id="BS-BAL-001",
        rule_name="资产=负债+所有者权益",
        passed=False,
        severity=Severity.ERROR,
        left_value=1234567.89,
        right_value=1234567.89,
        diff=0.0,
        tolerance=0.01,
        formula="asset_total == liability_total + equity_total",
        message="差额为 0.00，但因公式求值异常标记为未通过",
        category="A-表内平衡",
        trace=_make_trace(),
    )

    engine = DiagnosisEngine()
    diagnosis = engine.diagnose(result)

    print("=" * 60)
    print("诊断引擎验证输出")
    print("=" * 60)
    print(diagnosis)
    print("=" * 60)

    # 断言: 非空、中文、含关键部分
    assert len(diagnosis) > 0, "诊断输出为空"
    assert "BS-BAL-001" in diagnosis, "缺少规则 ID"
    assert "资产总计" in diagnosis, "缺少科目名称"
    assert "差额" in diagnosis, "缺少差额信息"
    assert "建议操作步骤" in diagnosis, "缺少操作步骤"
    # 确认无英文技术术语
    forbidden = ["error", "failed", "exception", "traceback", "tolerance"]
    for word in forbidden:
        assert word not in diagnosis.lower(), f"诊断输出包含英文技术术语: {word}"

    print("\n✅ 验证通过: 诊断输出为非空中文字符串，包含所有关键部分。")
    print("✅ 诊断引擎可正常使用。")


if __name__ == "__main__":
    main()
""":诊断引擎 (DiagnosisEngine) 测试: 规则驱动的中文诊断分析。

测试覆盖:
- 正常路径: BS-BAL-001 失败 + 完整 trace
- 差额量级: 极小 (<1元) / 较大 (>tolerance*100)
- 边界: 空 trace
- 规则分类: LR 类 -> 业务合理性提示
- 确定性: 同输入->同输出
- 中文输出: 无英文技术术语
"""

from __future__ import annotations

from fsa.agent.diagnosis import DiagnosisEngine
from fsa.core.models.result import TraceItem, ValidationResult
from fsa.core.models.rule import Severity


def _make_trace(items: list[tuple[str, str, float, int, str, str]]) -> list[TraceItem]:
    """快捷创建 trace 列表。

    tuple: (key, name, amount, row, column, side)
    """
    return [
        TraceItem(key=k, name=n, amount=a, row=r, column=c, side=s)
        for k, n, a, r, c, s in items
    ]


def _make_result(
    rule_id: str = "BS-BAL-001",
    rule_name: str = "资产=负债+所有者权益",
    diff: float = 10000.0,
    left_value: float = 1000000.0,
    right_value: float = 990000.0,
    tolerance: float = 0.01,
    category: str = "A-表内平衡",
    trace: list[TraceItem] | None = None,
    message: str = "差额超出容差",
) -> ValidationResult:
    if trace is None:
        trace = _make_trace([
            ("asset_total", "资产总计", 1000000.0, 35, "期末余额", "left"),
            ("liability_total", "负债合计", 600000.0, 20, "期末余额", "right"),
            ("equity_total", "所有者权益合计", 390000.0, 30, "期末余额", "right"),
        ])
    return ValidationResult(
        rule_id=rule_id,
        rule_name=rule_name,
        passed=False,
        severity=Severity.ERROR,
        left_value=left_value,
        right_value=right_value,
        diff=diff,
        tolerance=tolerance,
        formula="asset_total == liability_total + equity_total",
        message=message,
        category=category,
        trace=trace,
    )


class TestDiagnosisBasic:
    """诊断引擎基础功能测试。"""

    def test_diagnose_output_contains_rule_info(self) -> None:
        """诊断输出包含规则 ID、名称、差额信息。"""
        engine = DiagnosisEngine()
        result = _make_result()
        diagnosis = engine.diagnose(result)

        assert result.rule_id in diagnosis
        assert result.rule_name in diagnosis
        assert "差额" in diagnosis
        # 差额应格式化显示
        assert "10,000" in diagnosis

    def test_diagnose_output_contains_trace_subjects(self) -> None:
        """诊断输出包含涉及科目的名称、金额、行列定位。"""
        engine = DiagnosisEngine()
        result = _make_result()
        diagnosis = engine.diagnose(result)

        assert "资产总计" in diagnosis
        assert "负债合计" in diagnosis
        assert "所有者权益合计" in diagnosis
        assert "期末余额" in diagnosis
        assert "35" in diagnosis  # row
        assert "20" in diagnosis

    def test_diagnose_bs_bal_001_contains_fundamental_error_hint(self) -> None:
        """BS-BAL-001 不通过时提示根本性错误。"""
        engine = DiagnosisEngine()
        result = _make_result(rule_id="BS-BAL-001", diff=50000.0)
        diagnosis = engine.diagnose(result)

        assert "根本" in diagnosis or "恒等式" in diagnosis

    def test_diagnose_tiny_diff_suggests_rounding(self) -> None:
        """差额极小 (<1元) 时提示四舍五入/精度差异。"""
        engine = DiagnosisEngine()
        result = _make_result(diff=0.5)
        diagnosis = engine.diagnose(result)

        assert "四舍五入" in diagnosis or "精度" in diagnosis

    def test_diagnose_large_diff_suggests_deep_audit(self) -> None:
        """差额较大时提示重点核查。"""
        engine = DiagnosisEngine()
        result = _make_result(diff=50000.0, tolerance=0.01)
        diagnosis = engine.diagnose(result)

        assert "重点核查" in diagnosis or "核查" in diagnosis

    def test_diagnose_empty_trace_no_crash(self) -> None:
        """空 trace 不崩溃，输出说明无追溯信息。"""
        engine = DiagnosisEngine()
        result = _make_result(trace=[])
        diagnosis = engine.diagnose(result)

        assert "追溯" in diagnosis or "无" in diagnosis or "暂无" in diagnosis
        assert len(diagnosis) > 50  # 非空输出

    def test_diagnose_lr_category_uses_business_wording(self) -> None:
        """LR 类规则输出使用"业务合理性提示"措辞，不用"错误"。"""
        engine = DiagnosisEngine()
        result = _make_result(
            rule_id="LR-001",
            rule_name="净利润合理性检查",
            category="C-逻辑合理性",
            diff=5000.0,
        )
        diagnosis = engine.diagnose(result)

        assert "业务合理性" in diagnosis or "结合业务" in diagnosis

    def test_diagnose_cf_bal_001_mentions_fx_effect(self) -> None:
        """CF-BAL-001 提示检查汇率变动对现金的影响。"""
        engine = DiagnosisEngine()
        result = _make_result(
            rule_id="CF-BAL-001",
            rule_name="现金流量表平衡校验",
            category="A-表内平衡",
            diff=1000.0,
        )
        diagnosis = engine.diagnose(result)

        assert "汇率" in diagnosis

    def test_diagnose_deterministic_same_input_same_output(self) -> None:
        """确定性: 相同输入产生相同输出。"""
        engine = DiagnosisEngine()
        result = _make_result()

        d1 = engine.diagnose(result)
        d2 = engine.diagnose(result)

        assert d1 == d2


class TestDiagnosisChinese:
    """中文输出要求验证。"""

    def test_output_is_entirely_chinese_or_numbers(self) -> None:
        """诊断输出不包含英文技术术语。"""
        engine = DiagnosisEngine()
        result = _make_result()
        diagnosis = engine.diagnose(result)

        # 允许的英文: 规则 ID (如 BS-BAL-001) 和数字
        forbidden = ["error", "failed", "exception", "traceback", "tolerance"]
        for word in forbidden:
            assert word not in diagnosis.lower(), (
                f"诊断输出不应包含英文技术术语: {word}"
            )

    def test_output_contains_numbered_action_steps(self) -> None:
        """诊断输出包含编号的建议操作步骤。"""
        engine = DiagnosisEngine()
        result = _make_result()
        diagnosis = engine.diagnose(result)

        assert "1." in diagnosis or "一" in diagnosis
        assert "2." in diagnosis or "二" in diagnosis

    def test_diagnose_diff_at_tolerance_edge_contains_analysis(self) -> None:
        """差额为容差*100 边界时仍包含差额分析。"""
        engine = DiagnosisEngine()
        result = _make_result(diff=1.0, tolerance=0.01)
        diagnosis = engine.diagnose(result)

        assert "差额" in diagnosis
        assert len(diagnosis) > 100  # 有实质性内容
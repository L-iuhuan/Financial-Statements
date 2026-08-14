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

from fsa.agent.debate import DebateEngine
from fsa.agent.diagnosis import DiagnosisEngine
from fsa.agent.llm_client import DISCLAIMER_TEXT, ChatMessage
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


class TestDetailRuleAdvice:
    """明细层规则的针对性诊断建议。"""

    def test_cash_flow_detail_advice_mentions_scope(self) -> None:
        engine = DiagnosisEngine()
        result = _make_result(
            rule_id="CF-DTL-001",
            rule_name="现金流量明细=现金流量表",
            category="L2-明细勾稽",
            diff=15000000.0,
        )
        diagnosis = engine.diagnose(result)
        assert "口径" in diagnosis
        assert "受限资金" in diagnosis

    def test_trial_balance_advice_mentions_bad_debt(self) -> None:
        engine = DiagnosisEngine()
        result = _make_result(
            rule_id="TB-BS-001",
            rule_name="余额表=资产负债表",
            category="L2-明细勾稽",
            diff=2001.0,
        )
        diagnosis = engine.diagnose(result)
        assert "坏账准备" in diagnosis

    def test_cash_flow_classification_advice_is_review_hint(self) -> None:
        engine = DiagnosisEngine()
        result = _make_result(
            rule_id="CF-CLS-006",
            rule_name="现金流选择: 投资支付的现金",
            category="L4-现金流选择",
            diff=1.0,
        )
        diagnosis = engine.diagnose(result)
        assert "复核" in diagnosis

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


class TestExtractConfidence:
    """裁判结论置信度提取 (B-24): 正则兼容多种标注变体。"""

    def test_extract_high_with_ascii_colon(self) -> None:
        assert DebateEngine._extract_confidence("结论...置信度: 高，理由如下") == "高"

    def test_extract_high_with_fullwidth_colon(self) -> None:
        assert DebateEngine._extract_confidence("置信度：高") == "高"

    def test_extract_high_without_separator(self) -> None:
        assert DebateEngine._extract_confidence("综合判断置信度高") == "高"

    def test_extract_high_with_space(self) -> None:
        assert DebateEngine._extract_confidence("置信度 高") == "高"

    def test_extract_middle(self) -> None:
        assert DebateEngine._extract_confidence("置信度: 中") == "中"

    def test_extract_low(self) -> None:
        assert DebateEngine._extract_confidence("置信度：低") == "低"

    def test_fallback_to_middle_when_missing(self) -> None:
        """未标注置信度时设为「未标识」(P2 辩论增强)。"""
        assert DebateEngine._extract_confidence("没有置信度标注的结论") == "未标识"

    def test_fallback_to_middle_when_empty(self) -> None:
        assert DebateEngine._extract_confidence("") == "未标识"


class TestDiagnoseWithClientReasoning:
    """P1: diagnose_with_client 兼容推理模型 content 为空 (reasoning 兜底)。"""

    def test_reasoning_fallback_when_content_null(self) -> None:
        """content=null + reasoning 非空 -> 返回推理摘要而非规则化回退。"""

        class ReasoningLLM:
            base_url = "http://fake"
            model = "m"

            def is_available(self) -> bool:
                return True

            def chat(self, messages, tools=None, timeout=None):
                return ChatMessage(role="assistant", content="", reasoning="推理内容A")

            def chat_stream(
                self, messages, tools=None, timeout=None,
                on_chunk=None, on_reasoning_chunk=None,
            ):
                return self.chat(messages, tools=tools, timeout=timeout)

        engine = DiagnosisEngine()
        text = engine.diagnose_with_client(_make_result(), ReasoningLLM())
        assert "推理内容A" in text
        assert "max_tokens" in text

    def test_content_priority(self) -> None:
        """content 非空时使用正式内容, 不追加推理提示。"""

        class NormalLLM:
            base_url = "http://fake"
            model = "m"

            def is_available(self) -> bool:
                return True

            def chat(self, messages, tools=None, timeout=None):
                return ChatMessage(
                    role="assistant", content="正式诊断", reasoning="思考"
                )

            def chat_stream(
                self, messages, tools=None, timeout=None,
                on_chunk=None, on_reasoning_chunk=None,
            ):
                return self.chat(messages, tools=tools, timeout=timeout)

        engine = DiagnosisEngine()
        text = engine.diagnose_with_client(_make_result(), NormalLLM())
        # LLM 输出末尾追加 DISCLAIMER_TEXT (P0 免责标注)
        assert text.startswith("正式诊断")
        assert text.endswith(DISCLAIMER_TEXT)

    def test_empty_response_falls_back_to_rules(self) -> None:
        """content 与 reasoning 均为空 -> 回退规则化诊断。"""

        class EmptyLLM:
            base_url = "http://fake"
            model = "m"

            def is_available(self) -> bool:
                return True

            def chat(self, messages, tools=None, timeout=None):
                return ChatMessage(role="assistant", content="")

            def chat_stream(
                self, messages, tools=None, timeout=None,
                on_chunk=None, on_reasoning_chunk=None,
            ):
                return self.chat(messages, tools=tools, timeout=timeout)

        engine = DiagnosisEngine()
        text = engine.diagnose_with_client(_make_result(), EmptyLLM())
        assert "BS-BAL-001" in text


class TestDiagnosisDisclaimer:
    """P0 免责标注: 诊断输出后缀。"""

    def test_diagnose_ends_with_rule_engine_disclaimer(self) -> None:
        """规则化诊断末尾带「（规则引擎确定性诊断 · 未使用 AI）」标注。"""
        engine = DiagnosisEngine()
        text = engine.diagnose(_make_result())
        assert text.endswith("（规则引擎确定性诊断 · 未使用 AI）")

    def test_diagnose_with_client_fallback_includes_rule_engine_disclaimer(self) -> None:
        """LLM 不可用回退规则化诊断时同样带规则引擎标注。"""
        engine = DiagnosisEngine()
        text = engine.diagnose_with_client(_make_result(), client=None)
        assert text.endswith("（规则引擎确定性诊断 · 未使用 AI）")


class TestDebateOnStage:
    """P2 辩论增强: on_stage 回调按序调用 + 免责标注仅加最终结论。"""

    def test_on_stage_called_in_order(self) -> None:
        calls: list[str] = []

        class FakeLLM:
            base_url = "http://fake"
            model = "m"

            def is_available(self) -> bool:
                return True

            def chat(self, messages, tools=None, timeout=None):
                return ChatMessage(role="assistant", content="观点")

            def chat_stream(
                self, messages, tools=None, timeout=None,
                on_chunk=None, on_reasoning_chunk=None,
            ):
                return self.chat(messages, tools=tools, timeout=timeout)

        engine = DebateEngine(analyst=FakeLLM(), critic=FakeLLM(), judge=FakeLLM())
        engine.debate("case_data", on_stage=calls.append)
        assert calls == [
            "分析师正在分析…",
            "反方审计师正在质疑…",
            "裁判正在出具结论…",
        ]

    def test_only_final_verdict_has_disclaimer(self) -> None:
        class FakeLLM:
            base_url = "http://fake"
            model = "m"

            def is_available(self) -> bool:
                return True

            def chat(self, messages, tools=None, timeout=None):
                return ChatMessage(role="assistant", content="观点")

            def chat_stream(
                self, messages, tools=None, timeout=None,
                on_chunk=None, on_reasoning_chunk=None,
            ):
                return self.chat(messages, tools=tools, timeout=timeout)

        engine = DebateEngine(analyst=FakeLLM(), critic=FakeLLM(), judge=FakeLLM())
        result = engine.debate("case_data")
        # 仅最终结论追加免责标注, Analyst/Critic 中间发言不加
        assert result.final_verdict.endswith(DISCLAIMER_TEXT)
        assert not result.analyst_view.endswith(DISCLAIMER_TEXT)
        assert not result.critic_view.endswith(DISCLAIMER_TEXT)

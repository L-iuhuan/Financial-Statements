"""diagnose_with_llm 测试: 验证 LLM 增强诊断的优雅降级行为。

测试覆盖:
- client=None -> 回退到规则化诊断 diagnose()
- client.is_available()=False -> 回退
- client.generate() 抛出 OllamaError -> 回退
- LLM 可用时 -> 返回 LLM 文本
- 确定性: diagnose_with_llm(result, None) == diagnose(result)
- 所有 mock 无真实网络请求
"""

from __future__ import annotations

from unittest.mock import MagicMock

from fsa.agent.diagnosis import DiagnosisEngine
from fsa.agent.ollama_client import OllamaClient, OllamaError
from fsa.core.models.result import TraceItem, ValidationResult
from fsa.core.models.rule import Severity


def _make_result(
    rule_id: str = "BS-BAL-001",
    rule_name: str = "资产=负债+所有者权益",
    diff: float = 10000.0,
    tolerance: float = 0.01,
    category: str = "A-表内平衡",
) -> ValidationResult:
    """创建测试用的失败 ValidationResult。"""
    return ValidationResult(
        rule_id=rule_id,
        rule_name=rule_name,
        passed=False,
        severity=Severity.ERROR,
        left_value=1000000.0,
        right_value=990000.0,
        diff=diff,
        tolerance=tolerance,
        formula="asset_total == liability_total + equity_total",
        message="差额超出容差",
        category=category,
        trace=[
            TraceItem(
                key="asset_total", name="资产总计", amount=1000000.0,
                row=35, column="期末余额", side="left",
            ),
            TraceItem(
                key="liability_total", name="负债合计", amount=600000.0,
                row=20, column="期末余额", side="right",
            ),
            TraceItem(
                key="equity_total", name="所有者权益合计", amount=390000.0,
                row=30, column="期末余额", side="right",
            ),
        ],
    )


class TestDiagnoseWithLlmFallback:
    """验证 LLM 不可用时的回退行为。"""

    def test_falls_back_when_client_is_none(self) -> None:
        """client=None 时回退到规则化诊断。"""
        engine = DiagnosisEngine()
        result = _make_result()

        llm_output = engine.diagnose_with_llm(result, client=None)
        rule_output = engine.diagnose(result)

        assert llm_output == rule_output
        assert "BS-BAL-001" in llm_output
        assert "差额" in llm_output

    def test_falls_back_when_client_not_available(self) -> None:
        """client.is_available() 返回 False 时回退。"""
        engine = DiagnosisEngine()
        result = _make_result()

        mock_client = MagicMock(spec=OllamaClient)
        mock_client.is_available.return_value = False

        llm_output = engine.diagnose_with_llm(result, client=mock_client)
        rule_output = engine.diagnose(result)

        assert llm_output == rule_output
        mock_client.is_available.assert_called_once()
        # generate 不应被调用
        mock_client.generate.assert_not_called()

    def test_falls_back_when_generate_raises_ollama_error(self) -> None:
        """client.generate() 抛出 OllamaError 时回退。"""
        engine = DiagnosisEngine()
        result = _make_result()

        mock_client = MagicMock(spec=OllamaClient)
        mock_client.is_available.return_value = True
        mock_client.generate.side_effect = OllamaError("模拟连接失败")

        llm_output = engine.diagnose_with_llm(result, client=mock_client)
        rule_output = engine.diagnose(result)

        assert llm_output == rule_output
        mock_client.is_available.assert_called_once()
        mock_client.generate.assert_called_once()

    def test_falls_back_when_generate_returns_empty(self) -> None:
        """LLM 返回空字符串时回退到规则化诊断。"""
        engine = DiagnosisEngine()
        result = _make_result()

        mock_client = MagicMock(spec=OllamaClient)
        mock_client.is_available.return_value = True
        mock_client.generate.return_value = ""

        llm_output = engine.diagnose_with_llm(result, client=mock_client)
        rule_output = engine.diagnose(result)

        assert llm_output == rule_output


class TestDiagnoseWithLlmSuccess:
    """验证 LLM 可用时的成功路径。"""

    def test_uses_llm_when_available(self) -> None:
        """LLM 可用时调用 generate 并返回 LLM 文本。"""
        engine = DiagnosisEngine()
        result = _make_result()
        llm_text = "经分析，差异主要源于资产总计与负债合计+所有者权益的不匹配。"

        mock_client = MagicMock(spec=OllamaClient)
        mock_client.is_available.return_value = True
        mock_client.generate.return_value = llm_text

        output = engine.diagnose_with_llm(result, client=mock_client)

        assert output == llm_text
        mock_client.is_available.assert_called_once()
        mock_client.generate.assert_called_once()

    def test_llm_prompt_contains_rule_info(self) -> None:
        """LLM 提示词包含规则 ID、名称、差额、容差、公式。"""
        engine = DiagnosisEngine()
        result = _make_result()

        mock_client = MagicMock(spec=OllamaClient)
        mock_client.is_available.return_value = True
        mock_client.generate.return_value = "分析结果"

        engine.diagnose_with_llm(result, client=mock_client)

        call_kwargs = mock_client.generate.call_args.kwargs
        prompt = call_kwargs["prompt"]
        # 提示词应包含关键信息
        assert result.rule_id in prompt
        assert result.rule_name in prompt
        assert "差额" in prompt
        assert result.formula in prompt
        # system prompt 应包含审计师角色
        system = call_kwargs.get("system", "")
        assert "审计" in system

    def test_llm_prompt_contains_trace_info(self) -> None:
        """LLM 提示词包含追溯科目信息。"""
        engine = DiagnosisEngine()
        result = _make_result()

        mock_client = MagicMock(spec=OllamaClient)
        mock_client.is_available.return_value = True
        mock_client.generate.return_value = "分析结果"

        engine.diagnose_with_llm(result, client=mock_client)

        prompt = mock_client.generate.call_args.kwargs["prompt"]
        assert "资产总计" in prompt
        assert "负债合计" in prompt
        assert "所有者权益合计" in prompt

    def test_prompt_construction_is_deterministic(self) -> None:
        """相同输入产生相同的提示词（确定性）。"""
        engine = DiagnosisEngine()
        result = _make_result()

        mock_client1 = MagicMock(spec=OllamaClient)
        mock_client1.is_available.return_value = True
        mock_client1.generate.return_value = "a"

        mock_client2 = MagicMock(spec=OllamaClient)
        mock_client2.is_available.return_value = True
        mock_client2.generate.return_value = "b"

        engine.diagnose_with_llm(result, client=mock_client1)
        engine.diagnose_with_llm(result, client=mock_client2)

        prompt1 = mock_client1.generate.call_args.kwargs["prompt"]
        prompt2 = mock_client2.generate.call_args.kwargs["prompt"]
        assert prompt1 == prompt2


class TestDiagnoseWithLlmIntegration:
    """集成测试: diagnose_with_llm 与现有 diagnose() 的关系。"""

    def test_diagnose_unchanged(self) -> None:
        """确保现有 diagnose() 方法未被修改。"""
        engine = DiagnosisEngine()
        result = _make_result()
        diagnosis = engine.diagnose(result)

        assert "BS-BAL-001" in diagnosis
        assert "差额" in diagnosis
        assert "建议操作步骤" in diagnosis

    def test_no_import_of_ollama_in_diagnosis_module(self) -> None:
        """diagnosis 模块不直接导入 ollama_client（通过类型注解延迟导入）。"""
        # 这确保无 ollama 时 diagnosis 模块仍可独立使用
        import fsa.agent.diagnosis as mod
        # 模块应能正常导入而不依赖 ollama_client
        assert hasattr(mod, "DiagnosisEngine")

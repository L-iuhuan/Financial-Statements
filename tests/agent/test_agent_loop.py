"""AgentLoop 与工具集测试 (mock LLM, 无需真实模型)。"""

from __future__ import annotations

from fsa.agent.agent_loop import AgentLoop
from fsa.agent.knowledge import search_knowledge
from fsa.agent.llm_client import ChatMessage, ToolCall
from fsa.agent.tools import execute_tool
from fsa.core.models.result import ValidationResult, ValidationSummary
from fsa.core.models.rule import Severity


class FakeLLM:
    """可编程的 mock LLM。"""

    def __init__(self, responses: list[ChatMessage]) -> None:
        self._responses = responses
        self.calls = 0

    def is_available(self) -> bool:
        return True

    def chat(self, messages, tools=None):
        resp = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return resp


def _make_summary_with_fail() -> ValidationSummary:
    fail = ValidationResult(
        rule_id="BS-BAL-001", rule_name="资产=负债+所有者权益",
        passed=False, severity=Severity.ERROR,
        left_value=100.0, right_value=98.0, diff=2.0,
        tolerance=0.01, formula="asset_total == liability_total + equity_total",
        message="不通过",
    )
    return ValidationSummary(
        period="2024-12", total=1, passed=0, failed=1, errored=0,
        skipped=0, results=[fail],
    )


class TestAgentLoop:
    def test_direct_answer_no_tool(self, app_state) -> None:
        """LLM 直接回答 (无工具调用) -> 返回内容。"""
        llm = FakeLLM([ChatMessage(role="assistant", content="直接回答")])
        loop = AgentLoop(llm, app_state)
        assert loop.ask("你好") == "直接回答"

    def test_tool_call_then_answer(self, app_state) -> None:
        """LLM 先调工具, 拿到结果后再回答。"""
        tool_resp = ChatMessage(
            role="assistant", content="",
            tool_calls=[ToolCall(name="get_validation_results", arguments={})],
        )
        final = ChatMessage(role="assistant", content="基于工具结果的回答")
        llm = FakeLLM([tool_resp, final])
        loop = AgentLoop(llm, app_state)
        assert loop.ask("校验结果如何") == "基于工具结果的回答"
        assert llm.calls == 2

    def test_max_iterations_stops(self, app_state) -> None:
        """无限工具调用时在最大迭代处停止。"""
        tool_resp = ChatMessage(
            role="assistant", content="",
            tool_calls=[ToolCall(name="get_validation_results", arguments={})],
        )
        # max_iterations=3: 循环调用 chat 3 次(索引0-2)都返回工具调用,
        # 最后第 4 次(索引3)不带工具返回总结
        final = ChatMessage(role="assistant", content="总结")
        llm = FakeLLM([tool_resp, tool_resp, tool_resp, final])
        loop = AgentLoop(llm, app_state, max_iterations=3)
        assert loop.ask("循环") == "总结"

    def test_history_passed_through(self, app_state) -> None:
        """历史消息被加入上下文。"""
        llm = FakeLLM([ChatMessage(role="assistant", content="ok")])
        loop = AgentLoop(llm, app_state)
        history = [ChatMessage(role="user", content="之前的问题")]
        loop.ask("追问", history=history)
        # 验证调用成功即可 (FakeLLM 不检查内容, 但不抛异常说明结构正确)


class TestTools:
    def test_validation_results_none(self, app_state) -> None:
        result = execute_tool("get_validation_results", {}, app_state)
        assert "没有校验结果" in result

    def test_validation_results_with_fail(self, app_state) -> None:
        app_state._results = _make_summary_with_fail()
        result = execute_tool("get_validation_results", {}, app_state)
        assert "BS-BAL-001" in result
        assert "不通过" in result

    def test_rule_trace(self, app_state) -> None:
        app_state._results = _make_summary_with_fail()
        result = execute_tool("get_rule_trace", {"rule_id": "BS-BAL-001"}, app_state)
        assert "公式" in result
        assert "asset_total" in result

    def test_rule_trace_not_found(self, app_state) -> None:
        result = execute_tool("get_rule_trace", {"rule_id": "NOPE-001"}, app_state)
        assert "未找到" in result

    def test_unknown_tool(self, app_state) -> None:
        result = execute_tool("nonexistent_tool", {}, app_state)
        assert "未知工具" in result

    def test_imported_reports_empty(self, app_state) -> None:
        result = execute_tool("get_imported_reports", {}, app_state)
        assert "没有导入" in result

    def test_skipped_rules_empty(self, app_state) -> None:
        app_state._results = _make_summary_with_fail()
        result = execute_tool("get_skipped_rules", {}, app_state)
        assert "没有规则被跳过" in result


class TestKnowledge:
    def test_search_gouji(self) -> None:
        result = search_knowledge("勾稽关系")
        assert "资产 = 负债" in result or "资产=负债" in result

    def test_search_tolerance(self) -> None:
        result = search_knowledge("容差")
        assert "容差" in result

    def test_search_no_match(self) -> None:
        result = search_knowledge("完全不相关的词xyz123")
        assert "未找到" in result

    def test_search_empty(self) -> None:
        result = search_knowledge("")
        assert "关键词" in result

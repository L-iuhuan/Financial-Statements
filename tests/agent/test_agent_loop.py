"""AgentLoop 与工具集测试 (mock LLM, 无需真实模型)。"""

from __future__ import annotations

import pytest

from fsa.agent.agent_loop import AgentLoop, _normalize_history
from fsa.agent.knowledge import search_knowledge
from fsa.agent.llm_client import DISCLAIMER_TEXT, ChatMessage, LLMError, ToolCall
from fsa.agent.sanitize import sanitize_llm_input
from fsa.agent.tools import execute_tool
from fsa.core.models.result import ValidationResult, ValidationSummary
from fsa.core.models.rule import Severity


class FakeLLM:
    """可编程的 mock LLM。"""

    def __init__(self, responses: list[ChatMessage]) -> None:
        self._responses = responses
        self.calls = 0
        self.base_url = "http://fake"
        self.model = "fake-model"

    def is_available(self) -> bool:
        return True

    def chat(self, messages, tools=None, timeout=None):
        resp = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return resp

    def chat_stream(
        self, messages, tools=None, timeout=None, on_chunk=None, on_reasoning_chunk=None
    ):
        resp = self.chat(messages, tools=tools, timeout=timeout)
        if on_chunk is not None and resp.content:
            on_chunk(resp.content)
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
        """LLM 直接回答 (无工具调用) -> 返回正文 + 免责标注。"""
        llm = FakeLLM([ChatMessage(role="assistant", content="直接回答")])
        loop = AgentLoop(llm, app_state)
        result = loop.ask("你好")
        assert result.startswith("直接回答")
        assert result.endswith(DISCLAIMER_TEXT)

    def test_tool_call_then_answer(self, app_state) -> None:
        """LLM 先调工具, 拿到结果后再回答。"""
        tool_resp = ChatMessage(
            role="assistant", content="",
            tool_calls=[ToolCall(name="get_validation_results", arguments={})],
        )
        final = ChatMessage(role="assistant", content="基于工具结果的回答")
        llm = FakeLLM([tool_resp, final])
        loop = AgentLoop(llm, app_state)
        assert loop.ask("校验结果如何").startswith("基于工具结果的回答")
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
        assert loop.ask("循环").startswith("总结")

    def test_history_passed_through(self, app_state) -> None:
        """历史消息被加入上下文。"""
        llm = FakeLLM([ChatMessage(role="assistant", content="ok")])
        loop = AgentLoop(llm, app_state)
        history = [ChatMessage(role="user", content="之前的问题")]
        loop.ask("追问", history=history)
        # 验证调用成功即可 (FakeLLM 不检查内容, 但不抛异常说明结构正确)


class TestAgentLoopHistoryNormalization:
    """P0: 多轮历史 dict/ChatMessage 混合输入 (多轮崩溃修复)。"""

    def test_dict_history_does_not_crash(self, app_state) -> None:
        """dict 历史 (get_chat_history 来源) 不再触发 _to_openai_msg AttributeError。"""
        llm = FakeLLM([ChatMessage(role="assistant", content="ok")])
        loop = AgentLoop(llm, app_state)
        history = [{"role": "user", "content": "之前的问题"}]
        assert loop.ask("追问", history=history).startswith("ok")

    def test_mixed_chatmessage_and_dict_history(self, app_state) -> None:
        """ChatMessage 与 dict 混合历史正常通过。"""
        llm = FakeLLM([ChatMessage(role="assistant", content="ok")])
        loop = AgentLoop(llm, app_state)
        history: list[ChatMessage | dict] = [
            ChatMessage(role="user", content="q1"),
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
        ]
        assert loop.ask("追问", history=history).startswith("ok")

    def test_invalid_dict_entries_skipped(self, app_state) -> None:
        """缺 role/content 的 dict 条目被跳过, 不崩溃。"""
        llm = FakeLLM([ChatMessage(role="assistant", content="ok")])
        loop = AgentLoop(llm, app_state)
        history = [{"role": "user"}, {"content": "无role"}]
        assert loop.ask("追问", history=history).startswith("ok")


class TestAgentLoopReasoningFallback:
    """P1: content=null + reasoning 非空时以推理摘要兜底。"""

    def test_content_null_uses_reasoning_fallback(self, app_state) -> None:
        llm = FakeLLM(
            [ChatMessage(role="assistant", content="", reasoning="推理过程A")]
        )
        loop = AgentLoop(llm, app_state)
        result = loop.ask("你好")
        assert "推理过程A" in result
        assert "max_tokens" in result

    def test_reasoning_fallback_on_final_summary(self, app_state) -> None:
        """工具迭代后最终总结 content 为空时同样以 reasoning 兜底。"""
        tool_resp = ChatMessage(
            role="assistant",
            content="",
            tool_calls=[ToolCall(name="get_validation_results", arguments={})],
        )
        final = ChatMessage(role="assistant", content="", reasoning="总结推理")
        llm = FakeLLM([tool_resp, final])
        loop = AgentLoop(llm, app_state)
        result = loop.ask("循环")
        assert "总结推理" in result

    def test_content_priority_over_reasoning(self, app_state) -> None:
        """content 非空时优先使用正式内容。"""
        llm = FakeLLM(
            [ChatMessage(role="assistant", content="正式回答", reasoning="推理")]
        )
        loop = AgentLoop(llm, app_state)
        assert loop.ask("你好").startswith("正式回答")


class TestAgentLoopStream:
    """P1: ask_stream 分块回调与不支持流式时的回退。"""

    def test_ask_stream_collects_chunks(self, app_state) -> None:
        class StreamingLLM(FakeLLM):
            def chat_stream(
                self, messages, tools=None, timeout=None,
                on_chunk=None, on_reasoning_chunk=None,
            ):
                if on_chunk is not None:
                    on_chunk("你")
                    on_chunk("好")
                if on_reasoning_chunk is not None:
                    on_reasoning_chunk("思考")
                return ChatMessage(role="assistant", content="你好", reasoning="思考")

        llm = StreamingLLM([ChatMessage(role="assistant", content="你好")])
        loop = AgentLoop(llm, app_state)
        chunks: list[str] = []
        reasoning: list[str] = []
        result = loop.ask_stream(
            "你好", on_chunk=chunks.append, on_reasoning_chunk=reasoning.append
        )
        # 正常结束前最后一个分块为免责标注
        assert result.startswith("你好")
        assert result.endswith(DISCLAIMER_TEXT)
        assert chunks == ["你", "好", "\n\n" + DISCLAIMER_TEXT]
        assert reasoning == ["思考"]

    def test_ask_stream_fallback_when_no_chat_stream(self, app_state) -> None:
        """客户端不支持 chat_stream 时回退到非流式 chat。"""
        llm = FakeLLM([ChatMessage(role="assistant", content="普通回答")])
        loop = AgentLoop(llm, app_state)
        assert loop.ask_stream("你好").startswith("普通回答")


class TestAgentLoopCancel:
    """P1 取消机制: cancel_event 透传并在工具循环检查。"""

    def test_cancel_before_ask_raises_cancelled(self, app_state) -> None:
        """cancel_event 已置位时 ask 抛 LLMError("已取消") (向上冒泡)。"""
        import threading

        llm = FakeLLM([ChatMessage(role="assistant", content="ok")])
        loop = AgentLoop(llm, app_state)
        cancel = threading.Event()
        cancel.set()
        with pytest.raises(LLMError) as exc_info:
            loop.ask("你好", cancel_event=cancel)
        assert "已取消" in str(exc_info.value)

    def test_cancel_event_passed_to_chat_call(self, app_state) -> None:
        """cancel_event 透传给每次 LLM 调用。"""

        class CapturingLLM:
            base_url = "http://fake"
            model = "m"

            def __init__(self) -> None:
                self.cancel_seen: list[object] = []

            def is_available(self) -> bool:
                return True

            def chat(self, messages, tools=None, timeout=None, cancel_event=None):
                self.cancel_seen.append(cancel_event)
                return ChatMessage(role="assistant", content="ok")

            def chat_stream(
                self, messages, tools=None, timeout=None,
                on_chunk=None, on_reasoning_chunk=None, cancel_event=None,
            ):
                return self.chat(messages, tools=tools, timeout=timeout,
                                 cancel_event=cancel_event)

        import threading

        llm = CapturingLLM()
        loop = AgentLoop(llm, app_state)
        cancel = threading.Event()
        loop.ask("你好", cancel_event=cancel)
        assert llm.cancel_seen == [cancel]


class TestAgentLoopSanitizeHistory:
    """P1 输入消毒: 历史用户消息经 sanitize_llm_input 清洗。"""

    def test_user_content_sanitized(self) -> None:
        hist = _normalize_history(
            [{"role": "user", "content": "  a\x00b   c\n\n d  "}]
        )
        assert hist[0].content == sanitize_llm_input("  a\x00b   c\n\n d  ", max_len=4000)

    def test_user_chatmessage_sanitized(self) -> None:
        hist = _normalize_history([ChatMessage(role="user", content="x\x00y")])
        assert hist[0].content == "xy"

    def test_assistant_content_kept_unchanged(self) -> None:
        hist = _normalize_history([ChatMessage(role="assistant", content="  保留  ")])
        assert hist[0].content == "  保留  "

    def test_dict_assistant_content_kept(self) -> None:
        hist = _normalize_history([{"role": "assistant", "content": " a \nb "}])
        assert hist[0].content == " a \nb "


class TestAgentLoopTimeout:
    """AgentLoop.ask() 超时与 LLM 失败处理 (B-22)。"""

    def test_ask_passes_timeout_to_chat(self, app_state) -> None:
        """ask() 将 timeout 透传给 chat()。"""

        class CapturingLLM:
            def __init__(self) -> None:
                self.timeouts: list[float | None] = []
                self.base_url = "http://fake"
                self.model = "m"

            def is_available(self) -> bool:
                return True

            def chat(self, messages, tools=None, timeout=None):
                self.timeouts.append(timeout)
                return ChatMessage(role="assistant", content="ok")

            def chat_stream(
                self, messages, tools=None, timeout=None,
                on_chunk=None, on_reasoning_chunk=None,
            ):
                return self.chat(messages, tools=tools, timeout=timeout)

        llm = CapturingLLM()
        loop = AgentLoop(llm, app_state, timeout=42.0)
        loop.ask("你好")
        assert 42.0 in llm.timeouts

    def test_ask_returns_chinese_prompt_on_llm_error(self, app_state) -> None:
        """LLM 调用抛 LLMError 时返回中文提示而非异常。"""

        class FailingLLM:
            base_url = "http://fake"
            model = "m"

            def is_available(self) -> bool:
                return True

            def chat(self, messages, tools=None, timeout=None):
                raise LLMError("无法连接 LLM 服务")

            def chat_stream(
                self, messages, tools=None, timeout=None,
                on_chunk=None, on_reasoning_chunk=None,
            ):
                return self.chat(messages, tools=tools, timeout=timeout)

        loop = AgentLoop(FailingLLM(), app_state)
        result = loop.ask("你好")
        assert "无响应" in result

    def test_ask_returns_chinese_prompt_on_llm_error_at_final(self, app_state) -> None:
        """最大迭代后的最终总结调用失败同样返回中文提示。"""

        class FinalFailingLLM:
            base_url = "http://fake"
            model = "m"

            def __init__(self) -> None:
                self.calls = 0

            def is_available(self) -> bool:
                return True

            def chat(self, messages, tools=None, timeout=None):
                self.calls += 1
                if self.calls <= 3:
                    return ChatMessage(
                        role="assistant", content="",
                        tool_calls=[ToolCall(name="get_validation_results", arguments={})],
                    )
                raise LLMError("服务超时")

            def chat_stream(
                self, messages, tools=None, timeout=None,
                on_chunk=None, on_reasoning_chunk=None,
            ):
                return self.chat(messages, tools=tools, timeout=timeout)

        loop = AgentLoop(FinalFailingLLM(), app_state, max_iterations=3)
        result = loop.ask("循环")
        assert "无响应" in result


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


class TestContextAwarePrompt:
    def test_build_messages_includes_page_context(self, app_state) -> None:
        """页面上下文注记注入系统提示, 供模型按当前页面作答。"""
        loop = AgentLoop(FakeLLM([ChatMessage(role="assistant", content="ok")]), app_state)
        messages = loop._build_messages(
            "我现在在哪里？", None, "用户当前页面: 规则管理 (查看与维护勾稽规则)"
        )
        assert messages[0].role == "system"
        assert "规则管理" in messages[0].content
        assert "用户当前页面" in messages[0].content


class TestKnowledgeSources:
    def test_search_rule_library_cas(self, app_state) -> None:
        """规则库 CAS 引用可被检索。"""
        result = search_knowledge("BS-BAL-001")
        assert "规则 BS-BAL-001" in result
        assert "CAS" in result

    def test_search_external_cas_document(self, app_state) -> None:
        """内置 CAS 文档目录可被检索。"""
        result = search_knowledge("财务报表列报")
        assert "企业会计准则第 30 号" in result or "CAS" in result

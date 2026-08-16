"""LLM 客户端工厂与 provider 推断测试。"""

from __future__ import annotations

import io
import json
from unittest.mock import patch

import pytest

from fsa.agent.llm_client import (
    ChatMessage,
    LLMError,
    OllamaProvider,
    OpenAICompatProvider,
    ToolCall,
    _post_json,
    create_llm_client,
    infer_provider,
    is_local_url,
    response_text,
)
from fsa.core.exceptions import FSAError


class FakeStream(io.BytesIO):
    """模拟流式 HTTP 响应: 支持 with 与按行迭代。"""

    def __enter__(self) -> FakeStream:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class TestInferProvider:
    """根据服务地址推断 provider。"""

    def test_local_ollama_url_infers_ollama(self) -> None:
        assert infer_provider("http://localhost:11434") == "ollama"
        assert infer_provider("http://127.0.0.1:11434/") == "ollama"

    def test_v1_suffix_infers_openai(self) -> None:
        assert infer_provider("http://localhost:11434/v1") == "openai"
        assert infer_provider("http://10.16.2.6:4434/v1") == "openai"

    def test_remote_url_infers_openai(self) -> None:
        assert infer_provider("https://api.example.com/v1") == "openai"

    def test_empty_url_returns_empty(self) -> None:
        assert infer_provider("") == ""


class TestCreateClient:
    """工厂按 provider 创建对应客户端。"""

    def test_ollama_provider(self) -> None:
        client = create_llm_client("ollama", "http://localhost:11434", "qwen2.5:7b")
        assert client.__class__.__name__ == "OllamaProvider"

    def test_openai_provider(self) -> None:
        # 远程地址需显式 allow_remote (P0 离线守卫)
        client = create_llm_client(
            "openai", "http://10.16.2.6:4434/v1", "GLM-4.7-PF8", allow_remote=True
        )
        assert client.__class__.__name__ == "OpenAICompatProvider"


class TestIsLocalUrl:
    """P0 离线守卫: 地址是否为本地。"""

    def test_localhost_true(self) -> None:
        assert is_local_url("http://localhost:11434")

    def test_127_0_0_1_true(self) -> None:
        assert is_local_url("http://127.0.0.1:8000/v1")

    def test_ipv6_loopback_true(self) -> None:
        assert is_local_url("http://[::1]:11434")

    def test_zero_address_true(self) -> None:
        assert is_local_url("http://0.0.0.0:8000")

    def test_empty_url_true(self) -> None:
        assert is_local_url("")

    def test_no_scheme_localhost_true(self) -> None:
        assert is_local_url("localhost:11434")

    def test_internal_ip_false(self) -> None:
        assert not is_local_url("http://10.16.2.6:4434/v1")

    def test_domain_false(self) -> None:
        assert not is_local_url("https://api.example.com/v1")


class TestRemoteGuard:
    """P0 离线守卫: create_llm_client 拦截远程 openai 兼容连接。"""

    def test_remote_openai_blocked_by_default(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            create_llm_client("openai", "https://api.example.com/v1", "m")
        assert "远程" in str(exc_info.value)

    def test_remote_openai_allowed_when_flag(self) -> None:
        client = create_llm_client(
            "openai", "https://api.example.com/v1", "m", allow_remote=True
        )
        assert client.__class__.__name__ == "OpenAICompatProvider"

    def test_local_openai_not_blocked(self) -> None:
        client = create_llm_client("openai", "http://localhost:8000/v1", "m")
        assert client.__class__.__name__ == "OpenAICompatProvider"

    def test_ollama_unaffected_by_guard(self) -> None:
        client = create_llm_client("ollama", "http://localhost:11434", "qwen2.5:7b")
        assert client.__class__.__name__ == "OllamaProvider"


class TestPostJson:
    """_post_json 异常统一转为中文 LLMError (B-21)。"""

    def test_oserror_wrapped_as_llm_error(self) -> None:
        """OSError (网络不可达) -> LLMError 中文消息。"""
        with patch(
            "fsa.agent.llm_client.urlopen",
            side_effect=OSError("network unreachable"),
        ), pytest.raises(LLMError) as exc_info:
            _post_json("http://x/api/chat", {}, 60.0)
        assert "连接" in str(exc_info.value)

    def test_connection_refused_wrapped_as_llm_error(self) -> None:
        """ConnectionRefusedError (非 URLError 子类) -> LLMError。"""
        with patch(
            "fsa.agent.llm_client.urlopen",
            side_effect=ConnectionRefusedError("refused"),
        ), pytest.raises(LLMError) as exc_info:
            _post_json("http://x/api/chat", {}, 60.0)
        assert "连接" in str(exc_info.value)

    def test_urlerror_wrapped_as_llm_error(self) -> None:
        """URLError -> LLMError。"""
        from urllib.error import URLError

        with patch(
            "fsa.agent.llm_client.urlopen",
            side_effect=URLError("connection refused"),
        ), pytest.raises(LLMError):
            _post_json("http://x/api/chat", {}, 60.0)

    def test_timeout_wrapped_as_llm_error(self) -> None:
        """TimeoutError -> LLMError 中文超时消息。"""
        with patch(
            "fsa.agent.llm_client.urlopen",
            side_effect=TimeoutError("timed out"),
        ), pytest.raises(LLMError) as exc_info:
            _post_json("http://x/api/chat", {}, 60.0)
        assert "超时" in str(exc_info.value)


class TestRequiredParams:
    """构造器不提供硬编码默认值 (A6-001/008)。"""

    def test_ollama_provider_requires_base_url_and_model(self) -> None:
        with pytest.raises(TypeError):
            OllamaProvider()  # type: ignore[call-arg]

    def test_openai_provider_requires_base_url_and_model(self) -> None:
        with pytest.raises(TypeError):
            OpenAICompatProvider()  # type: ignore[call-arg]


class TestChatTimeout:
    """chat() 支持每次调用覆盖超时 (B-22)。"""

    def test_ollama_chat_accepts_timeout(self) -> None:
        client = OllamaProvider(base_url="http://localhost:11434", model="qwen2.5:7b")
        with patch(
            "fsa.agent.llm_client._post_json",
            return_value={"message": {"content": "ok"}},
        ) as mock_post:
            client.chat([ChatMessage(role="user", content="hi")], timeout=5.0)
        assert mock_post.call_args[0][2] == 5.0

    def test_openai_chat_accepts_timeout(self) -> None:
        client = OpenAICompatProvider(base_url="http://x/v1", model="m")
        with patch(
            "fsa.agent.llm_client._post_json",
            return_value={"choices": [{"message": {"content": "ok"}}]},
        ) as mock_post:
            client.chat([ChatMessage(role="user", content="hi")], timeout=7.0)
        assert mock_post.call_args[0][2] == 7.0


class TestToOpenAiMsgDict:
    """P0: _to_openai_msg 兼容 dict 与 ChatMessage 输入 (多轮崩溃修复)。"""

    def test_dict_user_message_accepted(self) -> None:
        """dict 输入不再访问 m.role, 直接取 role/content。"""
        result = OpenAICompatProvider._to_openai_msg(
            {"role": "user", "content": "你好"}
        )
        assert result == {"role": "user", "content": "你好"}

    def test_dict_tool_message_includes_tool_call_id(self) -> None:
        result = OpenAICompatProvider._to_openai_msg(
            {"role": "tool", "content": "结果", "tool_call_id": "call_1"}
        )
        assert result["tool_call_id"] == "call_1"

    def test_chat_message_still_works(self) -> None:
        """ChatMessage 输入保持原行为 (含 assistant tool_calls 序列化)。"""
        msg = ChatMessage(
            role="assistant",
            content="",
            tool_calls=[ToolCall(name="get_rule_trace", arguments={"rule_id": "x"})],
        )
        result = OpenAICompatProvider._to_openai_msg(msg)
        assert result["role"] == "assistant"
        assert result["tool_calls"][0]["function"]["name"] == "get_rule_trace"


class TestReasoningExtraction:
    """P1: 非流式解析提取 message.reasoning。"""

    def test_openai_chat_extracts_reasoning(self) -> None:
        client = OpenAICompatProvider(base_url="http://x/v1", model="m")
        with patch(
            "fsa.agent.llm_client._post_json",
            return_value={
                "choices": [{"message": {"content": "答", "reasoning": "思考"}}]
            },
        ):
            resp = client.chat([ChatMessage(role="user", content="q")])
        assert resp.content == "答"
        assert resp.reasoning == "思考"

    def test_openai_chat_reasoning_none_when_missing(self) -> None:
        client = OpenAICompatProvider(base_url="http://x/v1", model="m")
        with patch(
            "fsa.agent.llm_client._post_json",
            return_value={"choices": [{"message": {"content": "答"}}]},
        ):
            resp = client.chat([ChatMessage(role="user", content="q")])
        assert resp.reasoning is None

    def test_ollama_chat_extracts_reasoning(self) -> None:
        client = OllamaProvider(base_url="http://localhost:11434", model="m")
        with patch(
            "fsa.agent.llm_client._post_json",
            return_value={"message": {"content": "答", "reasoning": "思考"}},
        ):
            resp = client.chat([ChatMessage(role="user", content="q")])
        assert resp.reasoning == "思考"


class TestResponseTextFallback:
    """P1: content 为空 (max_tokens 耗尽于 reasoning) 时以 reasoning 尾部兜底。"""

    def test_content_priority(self) -> None:
        resp = ChatMessage(role="assistant", content="正式回答", reasoning="推理")
        assert response_text(resp) == "正式回答"

    def test_reasoning_fallback_when_content_empty(self) -> None:
        resp = ChatMessage(role="assistant", content="", reasoning="长推理")
        text = response_text(resp)
        assert text.startswith("长推理")
        assert "max_tokens" in text

    def test_reasoning_tail_limited(self) -> None:
        resp = ChatMessage(role="assistant", content="", reasoning="A" * 5000)
        text = response_text(resp, tail_chars=100)
        assert text.startswith("A" * 100)
        assert len(text) < 5000

    def test_both_empty_returns_empty(self) -> None:
        resp = ChatMessage(role="assistant", content="")
        assert response_text(resp) == ""


class TestOpenAIStream:
    """P1: OpenAI 兼容 SSE 流式解析 (content 分块 / tool_calls 增量拼接 / reasoning 通道)。"""

    def test_content_and_reasoning_chunk_order(self) -> None:
        sse = (
            'data: {"choices":[{"delta":{"reasoning":"思考"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"你"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"好"}}]}\n\n'
            'data: [DONE]\n\n'
        )
        client = OpenAICompatProvider(base_url="http://x/v1", model="m")
        chunks: list[str] = []
        reasoning: list[str] = []
        with patch(
            "fsa.agent.llm_client.urlopen",
            return_value=FakeStream(sse.encode("utf-8")),
        ):
            resp = client.chat_stream(
                [ChatMessage(role="user", content="q")],
                on_chunk=chunks.append,
                on_reasoning_chunk=reasoning.append,
            )
        assert chunks == ["你", "好"]
        assert reasoning == ["思考"]
        assert resp.content == "你好"
        assert resp.reasoning == "思考"

    def test_tool_calls_incremental_concatenation(self) -> None:
        sse = (
            'data: {"choices":[{"delta":{"tool_calls":['
            '{"index":0,"id":"call_1","function":{"name":"get_rule_trace",'
            '"arguments":"{\\"rule_id\\":\\""}}]}}]}\n\n'
            'data: {"choices":[{"delta":{"tool_calls":['
            '{"index":0,"function":{"arguments":"BS-BAL-001\\"}"}}]}}]}\n\n'
            'data: [DONE]\n\n'
        )
        client = OpenAICompatProvider(base_url="http://x/v1", model="m")
        with patch(
            "fsa.agent.llm_client.urlopen",
            return_value=FakeStream(sse.encode("utf-8")),
        ):
            resp = client.chat_stream([ChatMessage(role="user", content="q")])
        assert len(resp.tool_calls) == 1
        call = resp.tool_calls[0]
        assert call.name == "get_rule_trace"
        assert call.arguments == {"rule_id": "BS-BAL-001"}
        assert call.call_id == "call_1"

    def test_reasoning_content_alias_supported(self) -> None:
        sse = 'data: {"choices":[{"delta":{"reasoning_content":"思考中"}}]}\n\n'
        client = OpenAICompatProvider(base_url="http://x/v1", model="m")
        with patch(
            "fsa.agent.llm_client.urlopen",
            return_value=FakeStream(sse.encode("utf-8")),
        ):
            resp = client.chat_stream([ChatMessage(role="user", content="q")])
        assert resp.reasoning == "思考中"

    def test_stream_payload_includes_stream_and_max_tokens(self) -> None:
        sse = 'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'
        client = OpenAICompatProvider(base_url="http://x/v1", model="m", max_tokens=2048)
        with patch(
            "fsa.agent.llm_client.urlopen",
            return_value=FakeStream(sse.encode("utf-8")),
        ) as mock_urlopen:
            client.chat_stream([ChatMessage(role="user", content="q")])
        payload = json.loads(mock_urlopen.call_args[0][0].data)
        assert payload["stream"] is True
        assert payload["max_tokens"] == 2048


class TestOllamaStream:
    """P1: Ollama /api/chat 流式解析 (纯 JSON 行, 含 reasoning)。"""

    def test_content_and_reasoning(self) -> None:
        body = (
            '{"message":{"content":"你"}}\n'
            '{"message":{"content":"好"}}\n'
            '{"message":{"reasoning":"思考"}}\n'
            '{"message":{"content":"!"},"done":true}\n'
        )
        client = OllamaProvider(base_url="http://localhost:11434", model="m")
        chunks: list[str] = []
        reasoning: list[str] = []
        with patch(
            "fsa.agent.llm_client.urlopen",
            return_value=FakeStream(body.encode("utf-8")),
        ):
            resp = client.chat_stream(
                [ChatMessage(role="user", content="q")],
                on_chunk=chunks.append,
                on_reasoning_chunk=reasoning.append,
            )
        assert chunks == ["你", "好", "!"]
        assert reasoning == ["思考"]
        assert resp.content == "你好!"

    def test_stream_payload_has_stream_true(self) -> None:
        body = '{"message":{"content":"hi"}}\n'
        client = OllamaProvider(base_url="http://localhost:11434", model="m")
        with patch(
            "fsa.agent.llm_client.urlopen",
            return_value=FakeStream(body.encode("utf-8")),
        ) as mock_urlopen:
            client.chat_stream([ChatMessage(role="user", content="q")])
        payload = json.loads(mock_urlopen.call_args[0][0].data)
        assert payload["stream"] is True


class TestMaxTokens:
    """P1: 推理模型默认放宽 max_tokens (reasoning 消耗大)。"""

    def test_openai_default_4000(self) -> None:
        client = OpenAICompatProvider(base_url="http://x/v1", model="m")
        assert client.max_tokens == 4000

    def test_openai_override(self) -> None:
        client = OpenAICompatProvider(base_url="http://x/v1", model="m", max_tokens=8000)
        assert client.max_tokens == 8000

    def test_openai_chat_payload_includes_max_tokens(self) -> None:
        client = OpenAICompatProvider(base_url="http://x/v1", model="m")
        with patch(
            "fsa.agent.llm_client._post_json",
            return_value={"choices": [{"message": {"content": "ok"}}]},
        ) as mock_post:
            client.chat([ChatMessage(role="user", content="hi")])
        payload = mock_post.call_args[0][1]
        assert payload["max_tokens"] == 4000

    def test_ollama_default_no_limit(self) -> None:
        client = OllamaProvider(base_url="http://localhost:11434", model="m")
        assert client.max_tokens is None


class TestCancelEvent:
    """P1 取消机制: cancel_event 触发 chat/chat_stream 抛 LLMError("已取消")。"""

    def test_chat_cancelled_before_send_raises(self) -> None:
        """非流式 chat 在发送前检查取消, 不发起请求。"""
        import threading

        client = OpenAICompatProvider(base_url="http://localhost/v1", model="m")
        cancel = threading.Event()
        cancel.set()
        with patch("fsa.agent.llm_client._post_json") as mock_post, pytest.raises(
            LLMError
        ) as exc_info:
            client.chat([ChatMessage(role="user", content="q")], cancel_event=cancel)
        assert "已取消" in str(exc_info.value)
        mock_post.assert_not_called()

    def test_stream_cancelled_mid_stream_raises(self) -> None:
        """流式 chat_stream 逐行读取中发现取消即抛 LLMError("已取消")。"""
        import threading

        sse = (
            'data: {"choices":[{"delta":{"content":"你"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"好"}}]}\n\n'
            'data: [DONE]\n\n'
        )
        client = OpenAICompatProvider(base_url="http://x/v1", model="m")
        cancel = threading.Event()

        def on_chunk(text: str) -> None:
            # 收到第一个分块后触发取消, 下一轮迭代应抛异常
            cancel.set()

        with patch(
            "fsa.agent.llm_client.urlopen",
            return_value=FakeStream(sse.encode("utf-8")),
        ), pytest.raises(LLMError) as exc_info:
            client.chat_stream(
                [ChatMessage(role="user", content="q")],
                on_chunk=on_chunk,
                cancel_event=cancel,
            )
        assert "已取消" in str(exc_info.value)

    def test_ollama_stream_cancelled_raises(self) -> None:
        """Ollama 流式同样支持取消。"""
        import threading

        body = (
            '{"message":{"content":"你"}}\n'
            '{"message":{"content":"好"}}\n'
        )
        client = OllamaProvider(base_url="http://localhost:11434", model="m")
        cancel = threading.Event()
        cancel.set()
        with patch(
            "fsa.agent.llm_client.urlopen",
            return_value=FakeStream(body.encode("utf-8")),
        ), pytest.raises(LLMError) as exc_info:
            client.chat_stream(
                [ChatMessage(role="user", content="q")], cancel_event=cancel
            )
        assert "已取消" in str(exc_info.value)

    def test_stream_not_cancelled_completes(self) -> None:
        """未取消时流式正常完成 (取消参数不影响原行为)。"""
        import threading

        sse = 'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'
        client = OpenAICompatProvider(base_url="http://x/v1", model="m")
        cancel = threading.Event()
        with patch(
            "fsa.agent.llm_client.urlopen",
            return_value=FakeStream(sse.encode("utf-8")),
        ):
            resp = client.chat_stream(
                [ChatMessage(role="user", content="q")], cancel_event=cancel
            )
        assert resp.content == "hi"


class TestLLMErrorInheritance:
    """F6: LLMError 继承 FSAError。"""

    def test_llm_error_is_fsa_error(self) -> None:
        """LLMError 继承自 FSAError。"""
        assert issubclass(LLMError, FSAError)

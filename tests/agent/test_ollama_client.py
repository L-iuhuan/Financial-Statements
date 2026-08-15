"""OllamaClient 兼容层测试: 使用 unittest.mock 模拟 HTTP 请求，不连接真实服务器。

OllamaClient 是 llm_client.OllamaProvider 的兼容薄层，测试覆盖:
- is_available: 200 返回 True, URLError/TimeoutError 返回 False（委托 OllamaProvider）
- list_models: 正确解析 /api/tags 响应
- generate: 委托 OllamaProvider /api/chat, 正确构造对话消息并返回文本
- generate: HTTP 错误/JSON 解析失败 -> OllamaError
- chat: 委托 OllamaProvider 并返回 assistant 消息
- 兼容性: 构造签名 (base_url/model 必填)、方法名与 OllamaProvider 行为一致
- 确定性: 不依赖真实网络
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from fsa.agent.llm_client import ChatMessage, OllamaProvider
from fsa.agent.ollama_client import OllamaClient, OllamaError
from fsa.core.exceptions import FSAError


def _mock_response(body: dict, status: int = 200) -> MagicMock:
    """构造模拟的 HTTP 响应对象。"""
    mock_response = MagicMock()
    mock_response.status = status
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.read.return_value = json.dumps(body).encode("utf-8")
    return mock_response


class TestOllamaClientCompat:
    """兼容层结构验证: 委托 OllamaProvider。"""

    def test_is_subclass_of_provider(self) -> None:
        """OllamaClient 是 OllamaProvider 的子类（内部委托实现）。"""
        assert issubclass(OllamaClient, OllamaProvider)

    def test_chat_method_present(self) -> None:
        """chat 方法来自 OllamaProvider 且可调用。"""
        assert callable(OllamaClient.chat)

    def test_constructor_keeps_signature(self) -> None:
        """构造签名保留: base_url/model 必填, timeout 可选。"""
        client = OllamaClient(
            base_url="http://localhost:11434", model="qwen2.5:7b", timeout=10.0
        )
        assert client.base_url == "http://localhost:11434"
        assert client.model == "qwen2.5:7b"
        assert client.timeout == 10.0


class TestOllamaClientIsAvailable:
    """is_available() 测试: 委托 OllamaProvider 检查 /api/tags。"""

    def test_is_available_returns_true_on_200(self) -> None:
        """GET /api/tags 返回 200 -> is_available() 返回 True。"""
        client = OllamaClient(base_url="http://localhost:11434", model="qwen2.5:7b")

        with patch(
            "fsa.agent.llm_client.urlopen",
            return_value=_mock_response({}),
        ) as mock_urlopen:
            result = client.is_available()

        assert result is True
        mock_urlopen.assert_called_once()
        args = mock_urlopen.call_args[0][0]
        assert args.get_full_url() == "http://localhost:11434/api/tags"

    def test_is_available_returns_false_on_urlerror(self) -> None:
        """URLError (连接拒绝) -> is_available() 返回 False。"""
        client = OllamaClient(base_url="http://localhost:11434", model="qwen2.5:7b")

        with patch(
            "fsa.agent.llm_client.urlopen",
            side_effect=URLError("connection refused"),
        ):
            result = client.is_available()

        assert result is False

    def test_is_available_returns_false_on_timeout(self) -> None:
        """TimeoutError -> is_available() 返回 False。"""
        client = OllamaClient(base_url="http://localhost:11434", model="qwen2.5:7b")

        with patch(
            "fsa.agent.llm_client.urlopen",
            side_effect=TimeoutError("timed out"),
        ):
            result = client.is_available()

        assert result is False

    def test_is_available_returns_false_on_oserror(self) -> None:
        """OSError (如 socket error) -> is_available() 返回 False。"""
        client = OllamaClient(base_url="http://localhost:11434", model="qwen2.5:7b")

        with patch(
            "fsa.agent.llm_client.urlopen",
            side_effect=OSError("network unreachable"),
        ):
            result = client.is_available()

        assert result is False

    def test_is_available_returns_false_on_non_200(self) -> None:
        """GET /api/tags 返回非 200 -> is_available() 返回 False。"""
        client = OllamaClient(base_url="http://localhost:11434", model="qwen2.5:7b")

        with patch(
            "fsa.agent.llm_client.urlopen",
            return_value=_mock_response({}, status=500),
        ):
            result = client.is_available()

        assert result is False


class TestOllamaClientListModels:
    """list_models() 测试: 解析模型列表。"""

    def test_list_models_parses_tags_response(self) -> None:
        """正确解析 /api/tags 返回的模型名称列表。"""
        client = OllamaClient(base_url="http://localhost:11434", model="qwen2.5:7b")

        with patch(
            "fsa.agent.ollama_client.urlopen",
            return_value=_mock_response({
                "models": [
                    {"name": "qwen2.5:7b", "modified_at": "2025-01-01T00:00:00Z"},
                    {"name": "llama3.2:3b", "modified_at": "2025-01-01T00:00:00Z"},
                ]
            }),
        ):
            models = client.list_models()

        assert models == ["qwen2.5:7b", "llama3.2:3b"]

    def test_list_models_empty_when_no_models(self) -> None:
        """无模型时返回空列表。"""
        client = OllamaClient(base_url="http://localhost:11434", model="qwen2.5:7b")

        with patch(
            "fsa.agent.ollama_client.urlopen",
            return_value=_mock_response({"models": []}),
        ):
            models = client.list_models()

        assert models == []

    def test_list_models_raises_on_http_error(self) -> None:
        """HTTP 错误时抛出 OllamaError。"""
        client = OllamaClient(base_url="http://localhost:11434", model="qwen2.5:7b")

        with patch(
            "fsa.agent.ollama_client.urlopen",
            side_effect=URLError("server error"),
        ), pytest.raises(OllamaError):
            client.list_models()


class TestOllamaClientGenerate:
    """generate() 测试: 委托 OllamaProvider /api/chat 生成文本。"""

    def test_generate_delegates_to_chat_endpoint(self) -> None:
        """POST /api/chat 发送正确的对话载荷并返回文本。"""
        client = OllamaClient(
            base_url="http://localhost:11434", model="qwen2.5:7b"
        )

        with patch(
            "fsa.agent.llm_client.urlopen",
            return_value=_mock_response({
                "message": {"content": "分析结果: 差异源自尾差累积。"}
            }),
        ) as mock_urlopen:
            result = client.generate("请分析差异", system="你是审计师")

        assert result == "分析结果: 差异源自尾差累积。"
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert req.get_full_url() == "http://localhost:11434/api/chat"
        payload = json.loads(req.data)
        assert payload["model"] == "qwen2.5:7b"
        assert payload["stream"] is False
        messages = payload["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "你是审计师"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "请分析差异"

    def test_generate_default_no_system_message(self) -> None:
        """未提供 system 时不发送 system 消息。"""
        client = OllamaClient(base_url="http://localhost:11434", model="qwen2.5:7b")

        with patch(
            "fsa.agent.llm_client.urlopen",
            return_value=_mock_response({"message": {"content": "ok"}}),
        ) as mock_urlopen:
            client.generate("test")

        payload = json.loads(mock_urlopen.call_args[0][0].data)
        messages = payload["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "test"

    def test_generate_raises_ollama_error_on_http_error(self) -> None:
        """HTTP 错误时抛出 OllamaError（中文消息）。"""
        client = OllamaClient(base_url="http://localhost:11434", model="qwen2.5:7b")

        with patch(
            "fsa.agent.llm_client.urlopen",
            side_effect=URLError("connection refused"),
        ), pytest.raises(OllamaError) as exc_info:
            client.generate("test")

        assert "连接" in str(exc_info.value) or "Ollama" in str(exc_info.value)

    def test_generate_raises_ollama_error_on_timeout(self) -> None:
        """超时时抛出 OllamaError。"""
        client = OllamaClient(base_url="http://localhost:11434", model="qwen2.5:7b")

        with patch(
            "fsa.agent.llm_client.urlopen",
            side_effect=TimeoutError("timed out"),
        ), pytest.raises(OllamaError):
            client.generate("test")

    def test_generate_raises_ollama_error_on_json_decode_error(self) -> None:
        """响应非 JSON 时抛出 OllamaError。"""
        client = OllamaClient(base_url="http://localhost:11434", model="qwen2.5:7b")
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = b"not json"

        with patch(
            "fsa.agent.llm_client.urlopen", return_value=mock_response
        ), pytest.raises(OllamaError) as exc_info:
            client.generate("test")

        assert "解析" in str(exc_info.value) or "响应" in str(exc_info.value)

    def test_generate_raises_ollama_error_on_os_error(self) -> None:
        """OSError 时抛出 OllamaError。"""
        client = OllamaClient(base_url="http://localhost:11434", model="qwen2.5:7b")

        with patch(
            "fsa.agent.llm_client.urlopen",
            side_effect=OSError("socket error"),
        ), pytest.raises(OllamaError):
            client.generate("test")


class TestOllamaClientChat:
    """chat() 测试: 委托 OllamaProvider 并解析 assistant 消息。"""

    def test_chat_returns_assistant_message(self) -> None:
        """chat 返回包含 model 文本的 assistant ChatMessage。"""
        client = OllamaClient(base_url="http://localhost:11434", model="qwen2.5:7b")

        with patch(
            "fsa.agent.llm_client.urlopen",
            return_value=_mock_response({"message": {"content": "你好"}}),
        ) as mock_urlopen:
            response = client.chat([ChatMessage(role="user", content="你好")])

        assert response.role == "assistant"
        assert response.content == "你好"
        req = mock_urlopen.call_args[0][0]
        assert req.get_full_url() == "http://localhost:11434/api/chat"


class TestOllamaClientProviderConsistency:
    """兼容层与 OllamaProvider 行为一致性验证。"""

    def test_generate_consistent_with_provider_chat(self) -> None:
        """同一输入下 generate 与 OllamaProvider.chat 返回相同文本。"""
        client = OllamaClient(base_url="http://localhost:11434", model="qwen2.5:7b")
        provider = OllamaProvider(base_url="http://localhost:11434", model="qwen2.5:7b")
        content = "兼容层与 provider 输出一致"

        with patch(
            "fsa.agent.llm_client.urlopen",
            return_value=_mock_response({"message": {"content": content}}),
        ):
            gen_text = client.generate("请分析", system="你是审计师")
            provider_msg = provider.chat([
                ChatMessage(role="system", content="你是审计师"),
                ChatMessage(role="user", content="请分析"),
            ])

        assert gen_text == content
        assert gen_text == provider_msg.content


class TestOllamaClientCustomConfig:
    """自定义配置测试。"""

    def test_custom_base_url_and_model(self) -> None:
        """自定义 base_url 和 model 正确传递到 /api/chat。"""
        client = OllamaClient(
            base_url="http://192.168.1.100:11434",
            model="llama3.2:3b",
            timeout=10.0,
        )

        with patch(
            "fsa.agent.llm_client.urlopen",
            return_value=_mock_response({"message": {"content": "ok"}}),
        ) as mock_urlopen:
            client.generate("test")

        req = mock_urlopen.call_args[0][0]
        assert req.get_full_url() == "http://192.168.1.100:11434/api/chat"
        payload = json.loads(req.data)
        assert payload["model"] == "llama3.2:3b"


class TestOllamaError:
    """OllamaError 异常类测试。"""

    def test_ollama_error_is_exception(self) -> None:
        """OllamaError 继承自 FSAError。"""
        assert issubclass(OllamaError, FSAError)

    def test_ollama_error_str(self) -> None:
        """OllamaError 的字符串表示包含消息。"""
        err = OllamaError("连接失败")
        assert "连接失败" in str(err)


class TestOllamaRequiredParams:
    """构造器不提供硬编码默认值 (A6-001/008)。"""

    def test_client_requires_base_url_and_model(self) -> None:
        with pytest.raises(TypeError):
            OllamaClient()  # type: ignore[call-arg]

    def test_client_requires_base_url(self) -> None:
        with pytest.raises(TypeError):
            OllamaClient(model="qwen2.5:7b")  # type: ignore[call-arg]


class TestOllamaGenerateTimeout:
    """generate() 支持每次调用覆盖超时 (B-22)。"""

    def test_generate_accepts_timeout_override(self) -> None:
        client = OllamaClient(
            base_url="http://localhost:11434", model="qwen2.5:7b"
        )

        with patch(
            "fsa.agent.llm_client.urlopen",
            return_value=_mock_response({"message": {"content": "ok"}}),
        ) as mock_urlopen:
            client.generate("test", timeout=3.0)

        _, kwargs = mock_urlopen.call_args
        assert kwargs["timeout"] == 3.0

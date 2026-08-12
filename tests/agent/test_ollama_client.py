"""OllamaClient 测试: 使用 unittest.mock 模拟 HTTP 请求，不连接真实服务器。

测试覆盖:
- is_available: 200 返回 True, URLError/TimeoutError 返回 False
- list_models: 正确解析 /api/tags 响应
- generate: 正确构造 POST 请求并返回响应文本
- generate: HTTP 错误/JSON 解析失败 -> OllamaError
- 确定性: 不依赖真实网络
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from fsa.agent.ollama_client import OllamaClient, OllamaError


class TestOllamaClientIsAvailable:
    """is_available() 测试: 验证可用性检查逻辑。"""

    def test_is_available_returns_true_on_200(self) -> None:
        """GET /api/tags 返回 200 -> is_available() 返回 True。"""
        client = OllamaClient()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("fsa.agent.ollama_client.urlopen", return_value=mock_response) as mock_urlopen:
            result = client.is_available()

        assert result is True
        mock_urlopen.assert_called_once()
        args = mock_urlopen.call_args[0][0]
        assert args.get_full_url() == "http://localhost:11434/api/tags"

    def test_is_available_returns_false_on_urlerror(self) -> None:
        """URLError (连接拒绝) -> is_available() 返回 False。"""
        client = OllamaClient()

        with patch(
            "fsa.agent.ollama_client.urlopen",
            side_effect=URLError("connection refused"),
        ):
            result = client.is_available()

        assert result is False

    def test_is_available_returns_false_on_timeout(self) -> None:
        """TimeoutError -> is_available() 返回 False。"""
        client = OllamaClient()

        with patch(
            "fsa.agent.ollama_client.urlopen",
            side_effect=TimeoutError("timed out"),
        ):
            result = client.is_available()

        assert result is False

    def test_is_available_returns_false_on_oserror(self) -> None:
        """OSError (如 socket error) -> is_available() 返回 False。"""
        client = OllamaClient()

        with patch(
            "fsa.agent.ollama_client.urlopen",
            side_effect=OSError("network unreachable"),
        ):
            result = client.is_available()

        assert result is False

    def test_is_available_returns_false_on_non_200(self) -> None:
        """GET /api/tags 返回非 200 -> is_available() 返回 False。"""
        client = OllamaClient()
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("fsa.agent.ollama_client.urlopen", return_value=mock_response):
            result = client.is_available()

        assert result is False


class TestOllamaClientListModels:
    """list_models() 测试: 解析模型列表。"""

    def test_list_models_parses_tags_response(self) -> None:
        """正确解析 /api/tags 返回的模型名称列表。"""
        client = OllamaClient()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        raw = json.dumps({
            "models": [
                {"name": "qwen2.5:7b", "modified_at": "2025-01-01T00:00:00Z"},
                {"name": "llama3.2:3b", "modified_at": "2025-01-01T00:00:00Z"},
            ]
        }).encode("utf-8")
        mock_response.read.return_value = raw

        with patch("fsa.agent.ollama_client.urlopen", return_value=mock_response):
            models = client.list_models()

        assert models == ["qwen2.5:7b", "llama3.2:3b"]

    def test_list_models_empty_when_no_models(self) -> None:
        """无模型时返回空列表。"""
        client = OllamaClient()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = json.dumps({"models": []}).encode("utf-8")

        with patch("fsa.agent.ollama_client.urlopen", return_value=mock_response):
            models = client.list_models()

        assert models == []

    def test_list_models_raises_on_http_error(self) -> None:
        """HTTP 错误时抛出 OllamaError。"""
        client = OllamaClient()

        with patch(
            "fsa.agent.ollama_client.urlopen",
            side_effect=URLError("server error"),
        ), pytest.raises(OllamaError):
            client.list_models()


class TestOllamaClientGenerate:
    """generate() 测试: LLM 文本生成。"""

    def test_generate_posts_correct_payload(self) -> None:
        """POST /api/generate 发送正确的 JSON 载荷。"""
        client = OllamaClient(model="qwen2.5:7b")
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = json.dumps({
            "response": "分析结果: 差异源自尾差累积。"
        }).encode("utf-8")

        with patch("fsa.agent.ollama_client.urlopen", return_value=mock_response) as mock_urlopen:
            result = client.generate("请分析差异", system="你是审计师")

        assert result == "分析结果: 差异源自尾差累积。"
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert req.get_full_url() == "http://localhost:11434/api/generate"
        payload = json.loads(req.data)
        assert payload["model"] == "qwen2.5:7b"
        assert payload["prompt"] == "请分析差异"
        assert payload["system"] == "你是审计师"
        assert payload["stream"] is False

    def test_generate_default_system_prompt(self) -> None:
        """未提供 system 时使用空字符串。"""
        client = OllamaClient()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = json.dumps({"response": "ok"}).encode("utf-8")

        with patch("fsa.agent.ollama_client.urlopen", return_value=mock_response) as mock_urlopen:
            client.generate("test")

        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data)
        assert payload["system"] == ""

    def test_generate_raises_ollama_error_on_http_error(self) -> None:
        """HTTP 错误时抛出 OllamaError（中文消息）。"""
        client = OllamaClient()

        with patch(
            "fsa.agent.ollama_client.urlopen",
            side_effect=URLError("connection refused"),
        ), pytest.raises(OllamaError) as exc_info:
            client.generate("test")

        assert "连接" in str(exc_info.value) or "Ollama" in str(exc_info.value)

    def test_generate_raises_ollama_error_on_timeout(self) -> None:
        """超时时抛出 OllamaError。"""
        client = OllamaClient()

        with patch(
            "fsa.agent.ollama_client.urlopen",
            side_effect=TimeoutError("timed out"),
        ), pytest.raises(OllamaError):
            client.generate("test")

    def test_generate_raises_ollama_error_on_json_decode_error(self) -> None:
        """响应非 JSON 时抛出 OllamaError。"""
        client = OllamaClient()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = b"not json"

        with patch(
            "fsa.agent.ollama_client.urlopen", return_value=mock_response
        ), pytest.raises(OllamaError) as exc_info:
            client.generate("test")

        assert "解析" in str(exc_info.value) or "响应" in str(exc_info.value)

    def test_generate_raises_ollama_error_on_os_error(self) -> None:
        """OSError 时抛出 OllamaError。"""
        client = OllamaClient()

        with patch(
            "fsa.agent.ollama_client.urlopen",
            side_effect=OSError("socket error"),
        ), pytest.raises(OllamaError):
            client.generate("test")


class TestOllamaClientCustomConfig:
    """自定义配置测试。"""

    def test_custom_base_url_and_model(self) -> None:
        """自定义 base_url 和 model 正确传递。"""
        client = OllamaClient(
            base_url="http://192.168.1.100:11434",
            model="llama3.2:3b",
            timeout=10.0,
        )

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = json.dumps({"response": "ok"}).encode("utf-8")

        with patch("fsa.agent.ollama_client.urlopen", return_value=mock_response) as mock_urlopen:
            client.generate("test")

        req = mock_urlopen.call_args[0][0]
        assert req.get_full_url() == "http://192.168.1.100:11434/api/generate"
        payload = json.loads(req.data)
        assert payload["model"] == "llama3.2:3b"


class TestOllamaError:
    """OllamaError 异常类测试。"""

    def test_ollama_error_is_exception(self) -> None:
        """OllamaError 继承自 Exception。"""
        assert issubclass(OllamaError, Exception)

    def test_ollama_error_str(self) -> None:
        """OllamaError 的字符串表示包含消息。"""
        err = OllamaError("连接失败")
        assert "连接失败" in str(err)

"""LLM 客户端工厂与 provider 推断测试。"""

from __future__ import annotations

from fsa.agent.llm_client import create_llm_client, infer_provider


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
        client = create_llm_client("openai", "http://10.16.2.6:4434/v1", "GLM-4.7-PF8")
        assert client.__class__.__name__ == "OpenAICompatProvider"

"""Ollama 本地 LLM 客户端（兼容层）。

⚠️ 兼容层，新代码请用 fsa.agent.llm_client.OllamaProvider。
本模块为历史遗留的 OllamaClient，保留原构造签名（base_url/model 必填）
与方法名（is_available / generate / chat），内部全部委托给
llm_client.OllamaProvider（统一入口, /api/chat），供 scripts/verify_ollama.py
等旧调用方使用。新代码请优先使用 fsa.agent.llm_client.create_llm_client(provider="ollama")。

仅用 urllib.request, 不依赖第三方 HTTP 库。Ollama 不可用时整个应用正常
回退至规则化诊断, 不产生任何错误。
"""

from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from fsa.agent.llm_client import ChatMessage, LLMError, OllamaProvider
from fsa.core.exceptions import FSAError


class OllamaError(FSAError):
    """Ollama 客户端异常，所有错误信息使用中文。"""

    pass


class OllamaClient(OllamaProvider):
    """Ollama 本地 LLM 客户端（兼容层，新代码请用 fsa.agent.llm_client.OllamaProvider）。

    保留历史构造签名（base_url/model 必填）与方法名（is_available / generate /
    chat），内部全部委托给 OllamaProvider（/api/chat）。generate() 将 prompt/system
    转换为对话消息后调用 /api/chat，异常统一转译为 OllamaError 保持旧契约。

    Attributes:
        base_url: Ollama 服务地址（必填，无默认值）
        model: 使用的模型名称（必填，无默认值）
        timeout: 请求超时秒数，默认 30.0
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(base_url=base_url, model=model, timeout=timeout)

    def list_models(self) -> list[str]:
        """获取已安装的模型列表。

        Returns:
            模型名称列表，如 ["qwen2.5:7b", "llama3.2:3b"]

        Raises:
            OllamaError: 请求失败或响应解析失败
        """
        try:
            req = Request(
                f"{self.base_url}/api/tags",
                method="GET",
            )
            with urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (URLError, TimeoutError, OSError) as e:
            raise OllamaError(f"无法连接 Ollama 服务: {e}") from e
        except json.JSONDecodeError as e:
            raise OllamaError(f"Ollama 响应格式异常，无法解析模型列表: {e}") from e

        models = data.get("models", [])
        return [m["name"] for m in models if "name" in m]

    def generate(
        self,
        prompt: str,
        system: str = "",
        timeout: float | None = None,
    ) -> str:
        """调用 Ollama 生成文本（委托 OllamaProvider /api/chat）。

        Args:
            prompt: 用户提示词
            system: 系统提示词（角色设定），默认为空
            timeout: 本次请求超时秒数，None 时使用实例默认超时

        Returns:
            模型生成的文本

        Raises:
            OllamaError: 请求失败或响应解析失败（中文错误信息）
        """
        messages: list[ChatMessage] = []
        if system:
            messages.append(ChatMessage(role="system", content=system))
        messages.append(ChatMessage(role="user", content=prompt))
        try:
            response = self.chat(messages, timeout=timeout)
        except LLMError as e:
            raise OllamaError(str(e)) from e
        return response.content

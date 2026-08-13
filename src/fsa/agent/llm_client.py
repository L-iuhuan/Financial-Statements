"""LLM 客户端抽象层: provider 无关的对话接口。

支持:
- OllamaProvider: 本地 Ollama 服务 (/api/chat, 支持 tool calling)
- OpenAICompatProvider: OpenAI 兼容 API (公司本地 vLLM/FastChat 或在线 DeepSeek/通义)

仅用 Python 标准库 urllib, 不引入 requests (保护打包体积)。
无 LLM 可用时, 上层回退到规则化诊断, 不影响核心校验功能。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen


class LLMError(Exception):
    """LLM 客户端异常, 错误信息使用中文。"""


@dataclass
class ToolCall:
    """一次工具调用 (LLM 请求执行某个工具)。"""

    name: str
    arguments: dict
    call_id: str = ""


@dataclass
class ChatMessage:
    """一条对话消息。

    role: system / user / assistant / tool
    tool_calls: assistant 消息中 LLM 请求的工具调用列表
    tool_call_id: tool 消息对应的工具调用 id (OpenAI 兼容模式需要)
    """

    role: str
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str = ""


class LLMClient(Protocol):
    """LLM 客户端协议: 所有 provider 必须实现。"""

    def is_available(self) -> bool:
        """检查服务是否可用 (短超时, 不阻塞 UI)。"""
        ...

    def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
    ) -> ChatMessage:
        """发送对话, 返回 assistant 消息 (可能含 tool_calls)。"""
        ...


def _post_json(url: str, payload: dict, timeout: float, api_key: str = "") -> dict:
    """发送 JSON POST 请求并解析响应。"""
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = Request(url, data=data, method="POST", headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except URLError as e:
        raise LLMError(f"无法连接 LLM 服务 ({url}): {e}") from e
    except TimeoutError as e:
        raise LLMError(f"LLM 请求超时 ({timeout}秒): {e}") from e
    except json.JSONDecodeError as e:
        raise LLMError(f"LLM 响应无法解析: {e}") from e


class OllamaProvider:
    """Ollama 本地服务 provider (/api/chat, 原生支持 tools)。"""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b",
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def is_available(self) -> bool:
        try:
            req = Request(f"{self.base_url}/api/tags", method="GET")
            with urlopen(req, timeout=3.0) as resp:
                return resp.status == 200
        except (URLError, TimeoutError, OSError):
            return False

    def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
    ) -> ChatMessage:
        payload: dict = {
            "model": self.model,
            "messages": [self._to_ollama_msg(m) for m in messages],
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        data = _post_json(f"{self.base_url}/api/chat", payload, self.timeout)
        msg = data.get("message", {})
        return ChatMessage(
            role="assistant",
            content=msg.get("content", ""),
            tool_calls=self._parse_ollama_tools(msg.get("tool_calls", [])),
        )

    @staticmethod
    def _to_ollama_msg(m: ChatMessage) -> dict:
        msg: dict = {"role": m.role, "content": m.content}
        if m.role == "assistant" and m.tool_calls:
            msg["tool_calls"] = [
                {"function": {"name": tc.name, "arguments": tc.arguments}}
                for tc in m.tool_calls
            ]
        return msg

    @staticmethod
    def _parse_ollama_tools(raw: list) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for item in raw:
            fn = item.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append(ToolCall(name=fn.get("name", ""), arguments=args))
        return calls


class OpenAICompatProvider:
    """OpenAI 兼容 API provider (公司本地 vLLM/FastChat 或在线服务)。"""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def is_available(self) -> bool:
        try:
            req = Request(f"{self.base_url}/models", method="GET")
            if self.api_key:
                req.add_header("Authorization", f"Bearer {self.api_key}")
            with urlopen(req, timeout=3.0) as resp:
                return resp.status == 200
        except (URLError, TimeoutError, OSError):
            return False

    def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
    ) -> ChatMessage:
        payload: dict = {
            "model": self.model,
            "messages": [self._to_openai_msg(m) for m in messages],
        }
        if tools:
            payload["tools"] = tools
        data = _post_json(
            f"{self.base_url}/chat/completions", payload, self.timeout, self.api_key
        )
        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        return ChatMessage(
            role="assistant",
            content=msg.get("content") or "",
            tool_calls=self._parse_openai_tools(msg.get("tool_calls", [])),
        )

    @staticmethod
    def _to_openai_msg(m: ChatMessage) -> dict:
        msg: dict = {"role": m.role, "content": m.content}
        if m.role == "assistant" and m.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.call_id or f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for i, tc in enumerate(m.tool_calls)
            ]
        if m.role == "tool":
            msg["tool_call_id"] = m.tool_call_id
        return msg

    @staticmethod
    def _parse_openai_tools(raw: list) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for item in raw:
            fn = item.get("function", {})
            args = fn.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append(
                ToolCall(
                    name=fn.get("name", ""),
                    arguments=args,
                    call_id=item.get("id", ""),
                )
            )
        return calls


def create_llm_client(
    provider: str,
    base_url: str,
    model: str,
    api_key: str = "",
    timeout: float = 60.0,
) -> LLMClient:
    """工厂函数: 按 provider 类型创建 LLM 客户端。

    Args:
        provider: "ollama" 或 "openai"
        base_url: 服务地址
        model: 模型名称
        api_key: API 密钥 (openai 兼容模式可用)
        timeout: 超时秒数

    Returns:
        LLMClient 实例

    Raises:
        ValueError: 未知的 provider 类型
    """
    if provider == "ollama":
        return OllamaProvider(base_url=base_url, model=model, timeout=timeout)
    if provider == "openai":
        return OpenAICompatProvider(
            base_url=base_url, model=model, api_key=api_key, timeout=timeout
        )
    raise ValueError(f"未知的 LLM provider 类型: {provider}")


def infer_provider(base_url: str) -> str:
    """根据服务地址推断 provider 类型。

    用户只填地址、未选择模型类型时使用:
    - 含 localhost/127.0.0.1 且不含 /v1 后缀 → 本地 Ollama
    - 其余 → OpenAI 兼容 API
    """
    url = base_url.strip().lower()
    if not url:
        return ""
    is_local = "localhost" in url or "127.0.0.1" in url
    if is_local and not url.rstrip("/").endswith("/v1"):
        return "ollama"
    return "openai"

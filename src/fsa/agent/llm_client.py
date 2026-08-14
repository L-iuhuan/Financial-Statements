"""LLM 客户端抽象层: provider 无关的对话接口。

支持:
- OllamaProvider: 本地 Ollama 服务 (/api/chat, 支持 tool calling)
- OpenAICompatProvider: OpenAI 兼容 API (公司本地 vLLM/FastChat 或在线 DeepSeek/通义)

仅用 Python 标准库 urllib, 不引入 requests (保护打包体积)。
无 LLM 可用时, 上层回退到规则化诊断, 不影响核心校验功能。

流式 (chat_stream): SSE 逐行解析, delta.content / delta.reasoning 分块回调;
流式 tool_calls 按 index 增量拼接 arguments (GLM-4.7-PF8 实测格式)。
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from http.client import HTTPException, HTTPResponse
from typing import Protocol, cast
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from loguru import logger

# 推理模型 content 为空 (max_tokens 耗尽于 reasoning) 时, 附在 reasoning 兜底后的中文提示
REASONING_FALLBACK_HINT = "（模型推理过程较长，以上为推理摘要，建议增加 max_tokens）"

# AI 生成内容的免责标注 (P0): 所有对外展示的 LLM 最终输出末尾统一追加
DISCLAIMER_TEXT = (
    "⚠️ 以上内容由 AI 模型生成，仅供参考，不构成审计意见；最终判断请以规则引擎结果与人工复核为准。"
)

# 视为本机地址的 host 集合 (离线守卫, P0)
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

# 连续 SSE JSON 解析失败达到该阈值时记录一次警告 (P0, 防永久静默)
_SSE_PARSE_FAIL_WARN_THRESHOLD = 5


def _extract_host(url: str) -> str:
    """从服务地址中提取 host (小写)。

    兼容无 scheme 的地址 (如 "localhost:11434") 与 IPv6 简写 (如 "::1")。
    解析失败或地址为空时返回空字符串。
    """
    text = (url or "").strip()
    if not text:
        return ""
    if "://" not in text:
        # IPv6 地址需加方括号, 否则 ':' 会被误判为端口分隔
        if "::" in text and not text.startswith("["):
            text = f"[{text}]"
        text = f"http://{text}"
    try:
        return (urlsplit(text).hostname or "").lower()
    except ValueError:
        return ""


def is_local_url(url: str) -> bool:
    """判断服务地址是否指向本机 (离线守卫, P0)。

    仅当 host 属于 {localhost, 127.0.0.1, ::1, 0.0.0.0} 或为空时视为本地,
    其余 (含内网 IP 与域名) 一律视为远程, 由调用方决定是否放行。

    Args:
        url: LLM 服务地址 (base_url)

    Returns:
        True 表示本地地址, False 表示远程地址
    """
    host = _extract_host(url)
    return host == "" or host in _LOCAL_HOSTS


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
    reasoning: 推理模型的推理过程文本 (独立于 content, 可能为 None)
    """

    role: str
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str = ""
    reasoning: str | None = None


def response_text(response: ChatMessage, tail_chars: int = 1000) -> str:
    """取 assistant 消息的正式回复文本。

    content 非空时直接返回; content 为空 (推理模型 max_tokens 耗尽于 reasoning)
    时, 取 reasoning 尾部内容并附加中文提示兜底。
    """
    content = (response.content or "").strip()
    if content:
        return content
    reasoning = (response.reasoning or "").strip()
    if reasoning:
        return reasoning[-tail_chars:] + REASONING_FALLBACK_HINT
    return ""


class LLMClient(Protocol):
    """LLM 客户端协议: 所有 provider 必须实现。"""

    base_url: str
    model: str

    def is_available(self) -> bool:
        """检查服务是否可用 (短超时, 不阻塞 UI)。"""
        ...

    def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        timeout: float | None = None,
        cancel_event: threading.Event | None = None,
    ) -> ChatMessage:
        """发送对话 (非流式), 返回 assistant 消息 (可能含 tool_calls)。

        Args:
            timeout: 本次请求超时秒数, None 时使用实例默认超时。
            cancel_event: 取消事件, 发送前检查一次; urllib 阻塞请求无法中断,
                取消后仍需等到超时返回 (文档注明)。
        """
        ...

    def chat_stream(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        timeout: float | None = None,
        on_chunk: Callable[[str], None] | None = None,
        on_reasoning_chunk: Callable[[str], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> ChatMessage:
        """发送对话 (流式), 内容分块回调 on_chunk、推理分块回调 on_reasoning_chunk。

        完成后返回累积的完整 ChatMessage。LLM 调用失败时抛 LLMError。
        流式读取循环中每行检查 cancel_event, 已取消则抛 LLMError("已取消")。
        """
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
    except OSError as e:
        # ConnectionRefusedError 等非 URLError 子类在此统一转中文 LLMError
        raise LLMError(f"无法连接 LLM 服务 ({url}): {e}") from e
    except json.JSONDecodeError as e:
        raise LLMError(f"LLM 响应无法解析: {e}") from e


def _open_stream(
    url: str, payload: dict, timeout: float, api_key: str = ""
) -> HTTPResponse:
    """发起流式 POST 请求, 返回可迭代的响应对象 (连接异常统一转中文 LLMError)。"""
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = Request(url, data=data, method="POST", headers=headers)
    try:
        # urlopen 返回类型为 Any, 显式 cast 以满足 strict 类型检查 (运行时无副作用)
        return cast(HTTPResponse, urlopen(req, timeout=timeout))
    except URLError as e:
        raise LLMError(f"无法连接 LLM 服务 ({url}): {e}") from e
    except TimeoutError as e:
        raise LLMError(f"LLM 请求超时 ({timeout}秒): {e}") from e
    except OSError as e:
        raise LLMError(f"无法连接 LLM 服务 ({url}): {e}") from e


def _iter_sse_json(stream: Iterable[bytes]) -> Iterator[dict]:
    """从流式响应逐行解析 JSON 数据块。

    兼容 OpenAI SSE 格式 ("data: {...}") 与 Ollama 纯 JSON 行格式;
    跳过空行 / [DONE] / 无法解析的行。
    连续解析失败达到阈值时记录一次警告 (P0, 防永久静默)。
    """
    consecutive_failures = 0
    for raw_line in stream:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        payload = line[len("data:"):].strip() if line.startswith("data:") else line
        if not payload or payload == "[DONE]":
            continue
        try:
            yield json.loads(payload)
            consecutive_failures = 0
        except json.JSONDecodeError:
            consecutive_failures += 1
            if consecutive_failures == _SSE_PARSE_FAIL_WARN_THRESHOLD:
                logger.warning(
                    f"SSE 流式响应连续 {consecutive_failures} 行 JSON 解析失败并已静默跳过, "
                    "请检查 LLM 服务输出格式是否符合 SSE/纯 JSON 行"
                )


class OllamaProvider:
    """Ollama 本地服务 provider (/api/chat, 原生支持 tools)。

    base_url 与 model 必须显式传入, 不提供硬编码默认值
    (服务地址/模型名由用户在设置中配置)。
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 60.0,
        max_tokens: int | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        # Ollama 默认不限制输出长度; 显式传入时映射为 options.num_predict
        self.max_tokens = max_tokens

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
        timeout: float | None = None,
        cancel_event: threading.Event | None = None,
    ) -> ChatMessage:
        # 取消检查: urllib 阻塞请求无法中断, 发送前检查一次, 之后等待到超时
        if cancel_event is not None and cancel_event.is_set():
            raise LLMError("已取消")
        effective_timeout = timeout if timeout is not None else self.timeout
        payload: dict = {
            "model": self.model,
            "messages": [self._to_ollama_msg(m) for m in messages],
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        if self.max_tokens is not None:
            payload["options"] = {"num_predict": self.max_tokens}
        data = _post_json(f"{self.base_url}/api/chat", payload, effective_timeout)
        msg = data.get("message", {})
        return ChatMessage(
            role="assistant",
            content=msg.get("content", ""),
            reasoning=msg.get("reasoning") or None,
            tool_calls=self._parse_ollama_tools(msg.get("tool_calls", [])),
        )

    def chat_stream(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        timeout: float | None = None,
        on_chunk: Callable[[str], None] | None = None,
        on_reasoning_chunk: Callable[[str], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> ChatMessage:
        if cancel_event is not None and cancel_event.is_set():
            raise LLMError("已取消")
        effective_timeout = timeout if timeout is not None else self.timeout
        payload: dict = {
            "model": self.model,
            "messages": [self._to_ollama_msg(m) for m in messages],
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
        if self.max_tokens is not None:
            payload["options"] = {"num_predict": self.max_tokens}
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        try:
            resp = _open_stream(f"{self.base_url}/api/chat", payload, effective_timeout)
            with resp:
                for chunk in _iter_sse_json(resp):
                    if cancel_event is not None and cancel_event.is_set():
                        raise LLMError("已取消")
                    msg = chunk.get("message", {})
                    content = msg.get("content") or ""
                    if content:
                        content_parts.append(content)
                        if on_chunk is not None:
                            on_chunk(content)
                    reasoning = msg.get("reasoning") or ""
                    if reasoning:
                        reasoning_parts.append(reasoning)
                        if on_reasoning_chunk is not None:
                            on_reasoning_chunk(reasoning)
                    if msg.get("tool_calls"):
                        tool_calls = self._parse_ollama_tools(msg.get("tool_calls", []))
        except (URLError, OSError, TimeoutError) as e:
            raise LLMError(f"无法连接 LLM 服务 ({self.base_url}): {e}") from e
        except HTTPException as e:
            raise LLMError(f"LLM 流式响应中断: {e}") from e
        return ChatMessage(
            role="assistant",
            content="".join(content_parts),
            reasoning="".join(reasoning_parts) or None,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _to_ollama_msg(m: ChatMessage | dict) -> dict:
        if isinstance(m, dict):
            return {"role": m.get("role", "user"), "content": m.get("content", "")}
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
        max_tokens: int = 4000,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        # 推理模型 reasoning 消耗大, 默认放宽输出上限 (GLM-4.7-PF8 实测)
        self.max_tokens = max_tokens

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
        timeout: float | None = None,
        cancel_event: threading.Event | None = None,
    ) -> ChatMessage:
        # 取消检查: urllib 阻塞请求无法中断, 发送前检查一次, 之后等待到超时
        if cancel_event is not None and cancel_event.is_set():
            raise LLMError("已取消")
        effective_timeout = timeout if timeout is not None else self.timeout
        payload: dict = {
            "model": self.model,
            "messages": [self._to_openai_msg(m) for m in messages],
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
        data = _post_json(
            f"{self.base_url}/chat/completions",
            payload,
            effective_timeout,
            self.api_key,
        )
        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        return ChatMessage(
            role="assistant",
            content=msg.get("content") or "",
            reasoning=msg.get("reasoning") or None,
            tool_calls=self._parse_openai_tools(msg.get("tool_calls", [])),
        )

    def chat_stream(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        timeout: float | None = None,
        on_chunk: Callable[[str], None] | None = None,
        on_reasoning_chunk: Callable[[str], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> ChatMessage:
        if cancel_event is not None and cancel_event.is_set():
            raise LLMError("已取消")
        effective_timeout = timeout if timeout is not None else self.timeout
        payload: dict = {
            "model": self.model,
            "messages": [self._to_openai_msg(m) for m in messages],
            "stream": True,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_buffers: dict[int, tuple[str, str]] = {}
        arg_buffers: dict[int, str] = {}
        try:
            resp = _open_stream(
                f"{self.base_url}/chat/completions",
                payload,
                effective_timeout,
                self.api_key,
            )
            with resp:
                for chunk in _iter_sse_json(resp):
                    if cancel_event is not None and cancel_event.is_set():
                        raise LLMError("已取消")
                    for choice in chunk.get("choices", []):
                        self._consume_stream_delta(
                            choice.get("delta", {}),
                            content_parts,
                            reasoning_parts,
                            tool_buffers,
                            arg_buffers,
                            on_chunk,
                            on_reasoning_chunk,
                        )
        except (URLError, OSError, TimeoutError) as e:
            raise LLMError(f"无法连接 LLM 服务 ({self.base_url}): {e}") from e
        except HTTPException as e:
            raise LLMError(f"LLM 流式响应中断: {e}") from e
        return ChatMessage(
            role="assistant",
            content="".join(content_parts),
            reasoning="".join(reasoning_parts) or None,
            tool_calls=self._finalize_stream_tools(tool_buffers, arg_buffers),
        )

    @staticmethod
    def _consume_stream_delta(
        delta: dict,
        content_parts: list[str],
        reasoning_parts: list[str],
        tool_buffers: dict[int, tuple[str, str]],
        arg_buffers: dict[int, str],
        on_chunk: Callable[[str], None] | None,
        on_reasoning_chunk: Callable[[str], None] | None,
    ) -> None:
        reasoning = delta.get("reasoning") or delta.get("reasoning_content")
        if reasoning:
            reasoning_parts.append(reasoning)
            if on_reasoning_chunk is not None:
                on_reasoning_chunk(reasoning)
        content = delta.get("content")
        if content:
            content_parts.append(content)
            if on_chunk is not None:
                on_chunk(content)
        for tc in delta.get("tool_calls", []):
            index = tc.get("index", 0)
            fn = tc.get("function", {})
            name = fn.get("name") or ""
            args = fn.get("arguments") or ""
            existing = tool_buffers.get(index)
            if existing is None:
                tool_buffers[index] = (name, tc.get("id", ""))
                arg_buffers[index] = args
            else:
                tool_buffers[index] = (existing[0] + name, existing[1] or tc.get("id", ""))
                arg_buffers[index] = arg_buffers[index] + args

    @staticmethod
    def _finalize_stream_tools(
        tool_buffers: dict[int, tuple[str, str]], arg_buffers: dict[int, str]
    ) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for index in sorted(tool_buffers):
            name, call_id = tool_buffers[index]
            raw = arg_buffers.get(index, "")
            arguments: dict = {}
            if raw.strip():
                try:
                    arguments = json.loads(raw)
                except json.JSONDecodeError:
                    arguments = {}
            calls.append(ToolCall(name=name, arguments=arguments, call_id=call_id))
        return calls

    @staticmethod
    def _to_openai_msg(m: ChatMessage | dict) -> dict:
        if isinstance(m, dict):
            role = m.get("role", "user")
            dict_msg: dict = {"role": role, "content": m.get("content", "")}
            if role == "tool":
                dict_msg["tool_call_id"] = m.get("tool_call_id", "")
            return dict_msg
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
    *,
    allow_remote: bool = False,
) -> LLMClient:
    """工厂函数: 按 provider 类型创建 LLM 客户端。

    Args:
        provider: "ollama" 或 "openai"
        base_url: 服务地址
        model: 模型名称
        api_key: API 密钥 (openai 兼容模式可用)
        timeout: 超时秒数
        allow_remote: 是否允许连接远程服务 (P0 离线守卫, 默认 False:
            财务数据不允许离开本机, 远程 openai 兼容服务需显式开启)

    Returns:
        LLMClient 实例

    Raises:
        ValueError: 未知的 provider 类型, 或 openai 兼容服务为远程地址且未显式允许
    """
    if provider == "ollama":
        # Ollama 始终是本地服务, 不受离线守卫影响
        return OllamaProvider(base_url=base_url, model=model, timeout=timeout)
    if provider == "openai":
        if not allow_remote and not is_local_url(base_url):
            raise ValueError(
                "已阻止远程大模型连接：财务数据不允许离开本机。如确需远程服务，请在设置中显式开启。"
            )
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

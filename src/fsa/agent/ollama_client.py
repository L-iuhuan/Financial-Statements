"""Ollama 本地 LLM 客户端: 通过 urllib.request 调用 Ollama HTTP API。

不依赖第三方 HTTP 库（不使用 requests），仅使用 Python 标准库。
Ollama 不可用时整个应用正常回退至规则化诊断，不产生任何错误。
"""

from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen


class OllamaError(Exception):
    """Ollama 客户端异常，所有错误信息使用中文。"""

    pass


class OllamaClient:
    """Ollama 本地 LLM 客户端。

    使用 urllib.request 通过 HTTP API 与 Ollama 服务通信。
    所有方法均可安全调用——服务不可用时不会崩溃，返回 False 或空结果。

    Attributes:
        base_url: Ollama 服务地址，默认 http://localhost:11434
        model: 使用的模型名称，默认 qwen2.5:7b
        timeout: 请求超时秒数，默认 30.0
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b",
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def is_available(self) -> bool:
        """检查 Ollama 服务是否可用。

        通过 GET /api/tags 快速探测，使用短超时避免阻塞 UI。

        Returns:
            True 如果服务返回 200，否则 False
        """
        try:
            req = Request(
                f"{self.base_url}/api/tags",
                method="GET",
            )
            with urlopen(req, timeout=3.0) as resp:
                return resp.status == 200
        except (URLError, TimeoutError, OSError):
            return False

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

    def generate(self, prompt: str, system: str = "") -> str:
        """调用 Ollama 生成文本。

        Args:
            prompt: 用户提示词
            system: 系统提示词（角色设定），默认为空

        Returns:
            模型生成的文本

        Raises:
            OllamaError: 请求失败或响应解析失败（中文错误信息）
        """
        payload = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "system": system,
                "stream": False,
            }
        ).encode("utf-8")

        try:
            req = Request(
                f"{self.base_url}/api/generate",
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except URLError as e:
            raise OllamaError(f"无法连接 Ollama 服务 ({self.base_url}): {e}") from e
        except TimeoutError as e:
            raise OllamaError(f"Ollama 请求超时 ({self.timeout}秒): {e}") from e
        except OSError as e:
            raise OllamaError(f"Ollama 网络错误: {e}") from e

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise OllamaError(f"Ollama 返回内容无法解析: {e}") from e

        return data.get("response", "")

"""诊断代理模块: 规则化诊断 + 可选 LLM 增强 + AgentLoop 多轮对话。

支持 Ollama 本地模型与 OpenAI 兼容 API (公司本地/在线全参数模型)。
LLM 不可用时无缝回退到规则化诊断。
"""

from fsa.agent.agent_loop import AgentLoop
from fsa.agent.debate import DebateEngine, DebateResult
from fsa.agent.diagnosis import DiagnosisEngine
from fsa.agent.llm_client import (
    ChatMessage,
    LLMClient,
    LLMError,
    ToolCall,
    create_llm_client,
)
from fsa.agent.ollama_client import OllamaClient, OllamaError

__all__ = [
    "AgentLoop",
    "ChatMessage",
    "DebateEngine",
    "DebateResult",
    "DiagnosisEngine",
    "LLMClient",
    "LLMError",
    "OllamaClient",
    "OllamaError",
    "ToolCall",
    "create_llm_client",
]

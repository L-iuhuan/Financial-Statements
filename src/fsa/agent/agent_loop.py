"""Agent 对话循环: 多轮上下文 + 工具调用 + 分步推理。

这是 AI 助手的核心: 接收用户问题, 组装上下文和工具, 调用 LLM,
执行工具, 迭代直到 LLM 给出最终回答。
无 LLM 时由上层回退到规则化诊断 (本模块不处理回退)。
"""

from __future__ import annotations

from loguru import logger

from fsa.agent.llm_client import ChatMessage, LLMClient
from fsa.agent.tools import TOOL_SCHEMAS, execute_tool
from fsa.gui.app_state import AppState

# 系统提示词: 角色 + 推理展示要求
_SYSTEM_PROMPT = """你是一名资深财务审计师, 同时是这款"财务报表勾稽校验系统"的内置助手。

你的职责:
1. 解答财务勾稽、CAS 准则相关问题
2. 解释校验结果: 当某条规则不通过时, 用工具获取真实数据, 一步步推理差异根因
3. 指导软件使用

工作原则:
- 涉及具体校验结果/差额/科目数据时, 必须先调用工具获取真实数据, 不要臆测
- 解释差异时, 按以下结构分步说明:
  ① 校验内容: 这条规则校验什么
  ② 数据来源: 每个科目取自哪张表哪行哪列、金额多少 (用工具查)
  ③ 计算过程: 代入公式, 左右两侧各是多少
  ④ 差异定位: 差额是多少, 差异来自哪个科目
  ⑤ 可能原因: 结合财务知识分析根因
  ⑥ 建议操作: 给出排查或修正建议
- 回答使用中文, 面向财务人员, 不用技术术语
- 不确定时明确说明, 不要编造数据
"""


class AgentLoop:
    """AI 助手对话循环 (薄 agent)。

    职责: 多轮对话 + 工具调用迭代 + 分步推理展示。
    不修改任何校验数据, 只读 AppState。
    """

    def __init__(
        self,
        client: LLMClient,
        state: AppState,
        max_iterations: int = 5,
    ) -> None:
        self._client = client
        self._state = state
        self._max_iterations = max_iterations

    def ask(
        self,
        user_message: str,
        history: list[ChatMessage] | None = None,
    ) -> str:
        """处理一轮用户提问, 返回助手回答。

        Args:
            user_message: 用户问题
            history: 历史对话消息 (多轮上下文)

        Returns:
            助手的最终回答文本

        Raises:
            LLMError: LLM 服务异常 (由上层捕获并回退)
        """
        messages: list[ChatMessage] = [ChatMessage(role="system", content=_SYSTEM_PROMPT)]
        if history:
            messages.extend(history)
        messages.append(ChatMessage(role="user", content=user_message))

        for iteration in range(self._max_iterations):
            logger.debug(f"AgentLoop 第 {iteration + 1} 轮")
            response = self._client.chat(messages, tools=TOOL_SCHEMAS)

            # LLM 未请求工具 -> 直接返回最终回答
            if not response.tool_calls:
                return response.content

            # LLM 请求工具 -> 执行并把结果回传
            messages.append(response)
            for call in response.tool_calls:
                result = execute_tool(call.name, call.arguments, self._state)
                logger.debug(f"  工具 {call.name}({call.arguments}) -> {len(result)} 字")
                messages.append(
                    ChatMessage(
                        role="tool",
                        content=result,
                        tool_call_id=call.call_id,
                    )
                )

        # 达到最大迭代次数, 最后让 LLM 总结 (不带工具)
        logger.warning("AgentLoop 达到最大迭代次数, 强制总结")
        final = self._client.chat(messages, tools=None)
        return final.content

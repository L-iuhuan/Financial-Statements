"""多模型辩论引擎: 分析师-反方审计师-裁判三方对抗, 用于疑难差异的深度诊断。

角色:
- Analyst (分析师): 基于校验数据提出差异根因假设
- Critic (反方审计师): 质疑分析师, 提出反驳/替代解释 (职业怀疑)
- Judge (裁判): 综合双方, 给出最终可信结论 + 置信度

支持不同模型扮演不同角色 (如 pro 分析/裁判, flash 质疑)。
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from fsa.agent.llm_client import ChatMessage, LLMClient


@dataclass
class DebateResult:
    """辩论结果。"""

    analyst_view: str
    critic_view: str
    final_verdict: str
    confidence: str  # 高/中/低


_ANALYST_PROMPT = """你是一名资深财务审计分析师。基于给定的校验差异数据, 提出最可能的差异根因分析。
要求: 分步推理, 引用具体科目金额和行列位置, 给出 1-3 个按可能性排序的假设。用中文, 面向财务人员。"""

_CRITIC_PROMPT = """你是一名持有职业怀疑态度的反方审计师。你的任务是质疑分析师的诊断。
仔细阅读分析师的观点, 然后:
1. 指出其推理中的薄弱环节或未经证实的假设
2. 提出被忽略的替代解释
3. 质疑数据解读是否准确
不要简单地同意。用中文, 犀利但专业。"""

_JUDGE_PROMPT = """你是一名裁判审计合伙人。综合分析师的诊断和反方审计师的质疑, 给出最终结论。
要求:
1. 评估双方论点的证据强度
2. 给出最可信的差异根因结论
3. 标注置信度 (高/中/低) 及理由
4. 给出明确的排查建议
用中文, 面向财务人员, 客观中立。"""


class DebateEngine:
    """多模型辩论引擎。"""

    def __init__(
        self,
        analyst: LLMClient,
        critic: LLMClient,
        judge: LLMClient,
    ) -> None:
        self._analyst = analyst
        self._critic = critic
        self._judge = judge

    def debate(self, case_data: str) -> DebateResult:
        """对一个校验差异案例进行三方辩论。

        Args:
            case_data: 案例数据 (校验结果+追溯, 由调用方组装)

        Returns:
            DebateResult 三方观点 + 最终结论
        """
        # 第一轮: 分析师提出诊断
        logger.info("辩论轮1: 分析师诊断")
        analyst_view = self._analyst.chat([
            ChatMessage(role="system", content=_ANALYST_PROMPT),
            ChatMessage(role="user", content=f"校验差异数据:\n{case_data}"),
        ]).content

        # 第二轮: 反方质疑
        logger.info("辩论轮2: 反方审计师质疑")
        critic_view = self._critic.chat([
            ChatMessage(role="system", content=_CRITIC_PROMPT),
            ChatMessage(
                role="user",
                content=f"校验差异数据:\n{case_data}\n\n分析师的诊断:\n{analyst_view}",
            ),
        ]).content

        # 第三轮: 裁判综合
        logger.info("辩论轮3: 裁判综合裁决")
        verdict = self._judge.chat([
            ChatMessage(role="system", content=_JUDGE_PROMPT),
            ChatMessage(
                role="user",
                content=(
                    f"校验差异数据:\n{case_data}\n\n"
                    f"分析师观点:\n{analyst_view}\n\n"
                    f"反方质疑:\n{critic_view}"
                ),
            ),
        ]).content

        confidence = self._extract_confidence(verdict)
        return DebateResult(
            analyst_view=analyst_view,
            critic_view=critic_view,
            final_verdict=verdict,
            confidence=confidence,
        )

    @staticmethod
    def _extract_confidence(verdict: str) -> str:
        """从裁判结论中提取置信度标注。"""
        for level in ("高", "中", "低"):
            if f"置信度{level}" in verdict or f"置信度: {level}" in verdict or f"置信度：{level}" in verdict:
                return level
        return "未标注"

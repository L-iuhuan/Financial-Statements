"""AgentLoop 端到端验证: mock LLM 调用工具 + 多轮推理 + 知识检索。"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from fsa.agent.agent_loop import AgentLoop
from fsa.agent.llm_client import ChatMessage, ToolCall
from fsa.core.models.result import TraceItem, ValidationResult, ValidationSummary
from fsa.core.models.rule import Severity
from fsa.gui.app_state import AppState

# 构造一个带 trace 的失败校验结果
state = AppState()
fail = ValidationResult(
    rule_id="BS-BAL-001", rule_name="资产=负债+所有者权益",
    passed=False, severity=Severity.ERROR,
    left_value=128560000.0, right_value=128540000.0, diff=20000.0,
    tolerance=0.01, formula="asset_total == liability_total + equity_total",
    message="不通过",
    trace=[
        TraceItem(key="asset_total", name="资产总计", amount=128560000.0, row=35, column="期末余额", side="left"),
        TraceItem(key="liability_total", name="负债合计", amount=78420000.0, row=20, column="期末余额", side="right"),
        TraceItem(key="equity_total", name="所有者权益合计", amount=50140000.0, row=30, column="期末余额", side="right"),
    ],
)
state._results = ValidationSummary(
    period="2024-12", total=1, passed=0, failed=1, errored=0,
    skipped=0, results=[fail],
)


class ScriptedLLM:
    """模拟真实 LLM: 第一轮调 get_rule_trace, 第二轮给出分步推理。"""

    def __init__(self) -> None:
        self.calls = 0

    def is_available(self) -> bool:
        return True

    def chat(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            # 第一轮: 决定调用工具获取差异追溯
            return ChatMessage(
                role="assistant", content="",
                tool_calls=[ToolCall(name="get_rule_trace", arguments={"rule_id": "BS-BAL-001"})],
            )
        # 第二轮: 基于工具返回的真实数据, 给出分步推理
        last = messages[-1].content
        assert "资产总计" in last and "第35行" in last, "工具结果未正确回传"
        return ChatMessage(
            role="assistant",
            content=(
                "① 校验内容: 资产=负债+所有者权益恒等式\n"
                "② 数据来源: 资产总计取自资产负债表第35行期末余额(128,560,000元)\n"
                "③ 计算: 负债78,420,000 + 权益50,140,000 = 128,540,000元\n"
                "④ 差异: 20,000元, 左侧大于右侧\n"
                "⑤ 可能原因: 资产端多计或负债/权益端少计\n"
                "⑥ 建议: 核对第35行资产总计与各资产科目明细"
            ),
        )


loop = AgentLoop(ScriptedLLM(), state)
answer = loop.ask("BS-BAL-001 为什么不平? 数据是哪来的?")
print("=== AgentLoop 分步推理输出 ===")
print(answer)
print("\n=== 验证通过: LLM 调用工具获取真实数据并完成分步推理 ===")

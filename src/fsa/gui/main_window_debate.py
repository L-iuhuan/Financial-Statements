"""主窗口 AI 深度辩论集成 (mixin)。

从 main_window_agent 拆分的三方辩论 (DebateEngine) 集成逻辑 (纯移动, 不改行为)。
由 MainWindow 继承 (需与 MainWindowAgentMixin/MainWindowDrawerMixin 组合使用)。

依赖宿主 MainWindow 提供的属性: _state / _agent_drawer / _active_worker;
以及 MainWindowAgentMixin 提供的 _get_llm_client / _llm_available /
_set_agent_busy / _show_llm_error_infobar, MainWindowDrawerMixin 提供的 _open_drawer。
"""

from __future__ import annotations

from loguru import logger

from fsa.agent.debate import DebateResult
from fsa.agent.sanitize import sanitize_llm_input
from fsa.core.models.result import ValidationResult
from fsa.gui.agent_worker import AgentWorker
from fsa.gui.main_window_agent import _MainWindowAgentContracts

# PDF 来源行号编码基数 (与 core/importer/pdf_reader.py 的 _PDF_ROW_BASE 一致)
_PDF_ROW_BASE = 10_000_000


def _format_trace_loc(row: int, column: str) -> str:
    """追溯位置格式化: PDF 来源 (页码*1000万+表内行号) 解码为「第X页表内第N行」。"""
    if row <= 0:
        return column if column else "位置未知"
    if row >= _PDF_ROW_BASE:
        page, table_row = divmod(row, _PDF_ROW_BASE)
        return f"第{page}页表内第{table_row}行"
    return f"第{row}行 {column}列" if column else f"第{row}行"


class MainWindowDebateMixin(_MainWindowAgentContracts):
    """三方深度辩论集成逻辑 (继承 _MainWindowAgentContracts 提供跨 mixin 契约)。"""

    def _on_debate(self, rule_id: str) -> None:
        """从校验卡片触发深度辩论: 打开抽屉, 三方模型对抗分析差异根因。"""
        from fsa.agent.debate import DebateEngine

        summary = self._state.results
        if summary is None:
            self._agent_drawer.add_assistant_message(
                "当前没有校验结果，无法进行辩论分析。请先执行校验。"
            )
            return

        result = next((r for r in summary.results if r.rule_id == rule_id), None)
        if result is None:
            self._agent_drawer.add_assistant_message(
                f"未找到规则 {rule_id} 的校验结果。"
            )
            return

        client = self._get_llm_client()
        if client is None or not self._llm_available(client):
            if self._llm_block_reason == "remote":
                self._show_remote_blocked_infobar()
            self._agent_drawer.add_assistant_message(
                "深度辩论需要配置大模型。请在 系统设置 → AI 助手 中配置模型服务地址和密钥。"
            )
            return

        self._open_drawer()
        self._agent_drawer.set_context(rule_id, result.rule_name)
        self._agent_drawer.add_user_message(
            f"请对规则 {rule_id}（{result.rule_name}）进行深度辩论分析。"
        )
        self._agent_drawer.add_assistant_message(
            "**正在启动三方辩论分析**（分析师 → 反方审计师 → 裁判）\n"
            "请稍候，这需要调用多次大模型；可随时点击忙碌条上的「停止」中断。"
        )

        case_data = self._build_debate_case(result)
        self._set_agent_busy(True)

        def run_debate() -> str:
            engine = DebateEngine(analyst=client, critic=client, judge=client)
            # 阶段提示: 分析师/反方/裁判开始时推给抽屉 (designer 契约 set_stage_hint)
            debate = engine.debate(case_data, on_stage=self._debate_stage_hint)
            return self._format_debate_result(debate)

        def on_success(text: str) -> None:
            self._agent_drawer.add_assistant_message(text)

        def on_error(message: str) -> None:
            logger.error(f"深度辩论失败: {message}")
            self._finish_agent_error(message, "深度辩论失败")

        worker = AgentWorker(
            run_debate, on_success, on_error, on_finished=lambda: self._set_agent_busy(False)
        )
        self._active_worker = worker
        worker.start()

    def _debate_stage_hint(self, text: str) -> None:
        """把辩论阶段提示推给抽屉 (designer 契约: set_stage_hint)。"""
        drawer = getattr(self, "_agent_drawer", None)
        if drawer is not None and hasattr(drawer, "set_stage_hint"):
            drawer.set_stage_hint(text)

    def _build_debate_case(self, result: ValidationResult) -> str:
        """组装辩论案例数据 (校验结果 + 追溯)。

        来自报表数据的字段 (科目名/公式/来源定位等) 过 sanitize_llm_input (P1)。
        """
        lines = [
            f"规则: {sanitize_llm_input(result.rule_id)} "
            f"{sanitize_llm_input(result.rule_name)}",
            f"公式: {sanitize_llm_input(result.formula)}",
            f"左侧值: {result.left_value:,.2f} 元",
            f"右侧值: {result.right_value:,.2f} 元",
            f"差额: {result.diff:,.2f} 元 (容差 {sanitize_llm_input(str(result.tolerance))})",
            "涉及科目数据来源:",
        ]
        for t in result.trace:
            side = "左侧" if t.side == "left" else "右侧"
            loc = _format_trace_loc(t.row, sanitize_llm_input(t.column))
            lines.append(
                f"  [{side}] {sanitize_llm_input(t.name)}: "
                f"{t.amount:,.2f} 元 ({loc})"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_debate_result(debate: DebateResult) -> str:
        """将辩论结果格式化为 Markdown 展示文本 (气泡富文本渲染)。"""
        return (
            "**三方辩论分析完成**\n\n"
            f"### 分析师观点\n{debate.analyst_view}\n\n"
            f"### 反方审计师质疑\n{debate.critic_view}\n\n"
            f"### 裁判最终结论（置信度：{debate.confidence}）\n{debate.final_verdict}"
        )

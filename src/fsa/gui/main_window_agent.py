"""主窗口 AI 助手集成 (mixin)。

从 main_window 拆分的 AI 诊断/AgentLoop 集成逻辑 (纯移动, 不改行为)。
由 MainWindow 继承 (需与 MainWindowDrawerMixin/MainWindowDebateMixin 组合使用)。
三方辩论逻辑见 main_window_debate.py (MainWindowDebateMixin)。

依赖宿主 (MainWindow) 提供的属性: _state / _agent_drawer / _import_page /
_active_worker / _llm_availability (均在 __init__ / _setup_ui 中初始化)。
"""

from __future__ import annotations

import time

from loguru import logger
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QFrame, QPushButton
from qfluentwidgets import InfoBar, InfoBarPosition

from fsa.agent.diagnosis import DiagnosisEngine
from fsa.agent.llm_client import LLMClient
from fsa.gui.agent_worker import AgentWorker
from fsa.gui.app_state import AppState
from fsa.gui.pages.import_page import ImportPage
from fsa.gui.widgets.agent_drawer import AgentDrawer

# LLM 可用性探测结果的缓存 TTL (秒): 服务恢复后 60 秒内会重新探测
_LLM_AVAILABILITY_TTL_SECONDS = 60.0


class _MainWindowAgentContracts(QFrame):
    """跨 mixin 契约 (仅类型声明/桩方法, 运行时由实现方提供; 位于 MRO 末端)。

    MainWindowAgentMixin / MainWindowDebateMixin 均继承本契约,
    MainWindowDrawerMixin 提供 _open_drawer, MainWindowAgentMixin 提供
    _get_llm_client / _llm_available / _set_agent_busy / _show_llm_error_infobar。
    """

    _state: AppState
    _agent_drawer: AgentDrawer
    _active_worker: AgentWorker | None
    _llm_block_reason: str

    def _get_llm_client(self) -> LLMClient | None:
        """由 MainWindowAgentMixin 提供。"""
        raise NotImplementedError

    def _llm_available(self, client: LLMClient) -> bool:
        """由 MainWindowAgentMixin 提供。"""
        raise NotImplementedError

    def _open_drawer(self) -> None:
        """由 MainWindowDrawerMixin 提供。"""
        raise NotImplementedError

    def _set_agent_busy(self, busy: bool) -> None:
        """由 MainWindowAgentMixin 提供。"""
        raise NotImplementedError

    def _show_llm_error_infobar(self, message: str) -> None:
        """由 MainWindowAgentMixin 提供。"""
        raise NotImplementedError

    def _show_remote_blocked_infobar(self) -> None:
        """由 MainWindowAgentMixin 提供 (P0 离线守卫被拦截时的用户提示)。"""
        raise NotImplementedError

    def _finish_agent_error(self, message: str, prefix: str) -> None:
        """由 MainWindowAgentMixin 提供 (统一失败处理, 含取消安静路径)。"""
        raise NotImplementedError


class MainWindowAgentMixin(_MainWindowAgentContracts):
    """AI 助手集成逻辑: 诊断/AgentLoop 的后台线程编排 (继承 QFrame 以便访问 QWidget 方法)。

    以下属性/方法由宿主 MainWindow 提供 (main_window.py __init__/_setup_ui):
    _state (AppState), _agent_drawer (AgentDrawer), _import_page (ImportPage),
    _active_worker, _llm_availability, _open_drawer()。
    """

    _import_page: ImportPage
    _llm_availability: dict[str, tuple[bool, float]]
    # 最近一次 _get_llm_client 的拦截原因标记: "" 未拦截 / "remote" 远程未确认
    _llm_block_reason: str = ""
    # 抽屉取消信号是否已接线 (幂等保护)
    _drawer_cancel_connected: bool = False

    def _update_suggestions(self) -> None:
        """根据校验结果动态更新 AI 助手的建议气泡。"""
        summary = self._state.results
        suggestions: list[str] = []
        if summary is not None and summary.failed > 0:
            # 有不通过规则 -> 推荐诊断前 2 条失败规则
            failed = [r for r in summary.results if not r.passed and not r.errored]
            for r in failed[:2]:
                suggestions.append(f"诊断 {r.rule_id}")
            suggestions.append("为什么有规则不通过")
        elif summary is not None:
            # 全部通过
            suggestions = ["校验全部通过意味着什么", "如何导出审计底稿", "什么是勾稽关系"]
        else:
            # 默认
            suggestions = ["什么是勾稽关系", "BS-BAL-001 规则", "差额超容差怎么办"]
        self._agent_drawer.set_suggestions(suggestions[:3])

    def _on_agent_send(self, text: str) -> None:
        """处理用户发送的消息: 优先 AgentLoop (多轮+工具), 无 LLM 回退规则化。

        如果当前有规则上下文，则对该规则进行诊断分析；
        否则用 AgentLoop 进行多轮对话 + 工具调用;
        无 LLM 时给出通用的中文帮助提示。
        """
        logger.info(f"AI 助手收到消息: {text}")
        from fsa.agent.fallback import fallback_answer
        rule_id = self._agent_drawer.context_rule_id

        if rule_id is not None:
            self._diagnose_rule(rule_id)
            return

        # 尝试 AgentLoop (多轮对话 + 工具调用)
        client = self._get_llm_client()
        if client is not None:
            if self._llm_available(client):
                self._run_agent_loop(client, text)
                return
            self._agent_drawer.add_assistant_message(
                "检测到已配置大模型，但服务暂时不可用。以下先给出规则化答复：\n\n"
                + fallback_answer(text, self._state)
            )
            return

        # 远程地址被离线守卫拦截 -> 提示用户到设置中显式开启
        if self._llm_block_reason == "remote":
            self._show_remote_blocked_infobar()

        # 无 LLM: 智能规则化回退 (规则查询/知识库, 而非固定文本)
        self._agent_drawer.add_assistant_message(
            fallback_answer(text, self._state)
        )

    def _llm_available(self, client: LLMClient) -> bool:
        """检查 LLM 可用性 (按地址/模型键控缓存 + TTL, 60 秒后重新探测)。

        缓存键为 base_url|model, 配置变更自然失效;
        TTL 保证服务恢复后缓存的 False 不会永久生效。
        """
        key = f"{client.base_url}|{client.model}"
        cached = self._llm_availability.get(key)
        if cached is not None:
            available, cached_at = cached
            if time.monotonic() - cached_at < _LLM_AVAILABILITY_TTL_SECONDS:
                return available
        try:
            available = bool(client.is_available())
        except Exception:
            # 防御性兜底: 自定义 provider 的 is_available 可能抛任意异常,
            # 一律视为不可用 (宁可提示不可用, 不崩溃)
            logger.debug(f"LLM 可用性探测失败: {client.base_url}|{client.model}")
            available = False
        self._llm_availability[key] = (available, time.monotonic())
        return available

    def _run_agent_loop(self, client: LLMClient, text: str) -> None:
        """在后台线程流式运行 AgentLoop, 分块经 QMetaObject 回传主线程逐字渲染。

        reasoning 分块先显示在"思考过程"弱化区, 正式内容随后流入气泡;
        客户端不支持流式时回退为非流式一次性呈现。
        """
        history = self._agent_drawer.get_chat_history(limit=10)
        handle = self._agent_drawer.start_stream_message()

        def run() -> str:
            from fsa.agent.agent_loop import AgentLoop
            loop = AgentLoop(client, self._state)
            return loop.ask_stream(
                text,
                history=history,
                on_chunk=lambda chunk: worker.emit_chunk(chunk),
                on_reasoning_chunk=lambda chunk: worker.emit_reasoning_chunk(chunk),
            )

        def on_chunk(chunk: str) -> None:
            self._agent_drawer.append_stream_chunk(handle, chunk)

        def on_reasoning_chunk(chunk: str) -> None:
            self._agent_drawer.append_stream_reasoning(handle, chunk)

        def on_success(answer: str) -> None:
            # 客户端不支持流式 (回退非流式) 时, 无分块回传 -> 一次性填充
            if not handle.bubble.text() and answer:
                self._agent_drawer.append_stream_chunk(handle, answer)
            self._agent_drawer.finish_stream_message(handle)

        def on_error(message: str) -> None:
            logger.error(f"AgentLoop 失败: {message}")
            self._agent_drawer.finish_stream_message(handle)
            if self._is_cancelled_error(message):
                # 用户主动取消: 安静停止, 不弹错误提示
                self._agent_drawer.add_assistant_message("已停止生成。")
                return
            self._agent_drawer.add_assistant_message(
                f"AI 分析暂时不可用: {message}\n\n建议您检查大模型服务是否正常运行。"
            )

        worker = AgentWorker(
            run,
            on_success,
            on_error,
            on_finished=lambda: self._set_agent_busy(False),
            on_chunk=on_chunk,
            on_reasoning_chunk=on_reasoning_chunk,
        )
        self._active_worker = worker
        self._set_agent_busy(True)
        worker.start()

    def _on_diagnose(self, rule_id: str) -> None:
        """从校验卡片触发 AI 诊断: 打开抽屉、设上下文、运行诊断。"""
        self._open_drawer()
        rule_name = rule_id
        registry = self._state.registry
        if registry is not None:
            rule = registry.get_by_id(rule_id)
            if rule is not None:
                rule_name = rule.name
        self._agent_drawer.set_context(rule_id, rule_name)
        prompt = f"请诊断校验规则 {rule_id}（{rule_name}）未通过的原因，分析可能的差异根因。"
        self._agent_drawer.add_user_message(prompt)
        self._diagnose_rule(rule_id)

    def _get_llm_client(self) -> LLMClient | None:
        """根据设置构建 LLM 客户端 (QSettings 是唯一配置源, 无 Ollama 独立分支)。

        从 QSettings 读取 llm_provider/llm_base_url/llm_model/llm_api_key。
        返回 LLMClient 或 None (未配置 / 远程地址未显式确认风险)。

        拦截原因记录在 self._llm_block_reason (纯函数, 不弹窗):
        - "" : 未拦截 (正常返回 client 或仅未配置)
        - "remote": 远程 openai 兼容地址且 llm_allow_remote_ack 未开启 (返回 None)
        """
        from fsa.agent.llm_client import create_llm_client, infer_provider, is_local_url

        self._llm_block_reason = ""
        settings = QSettings("FSA", "FinancialAudit")
        provider = str(settings.value("llm_provider", ""))
        base_url = str(settings.value("llm_base_url", ""))
        model = str(settings.value("llm_model", ""))
        api_key = str(settings.value("llm_api_key", ""))
        if not base_url:
            # 服务地址为空: 跳过 LLM 功能 (由调用方给出中文提示, 不崩溃)
            return None
        if not model:
            # 只配服务地址未配模型名: 无法发起请求, 跳过 LLM 功能
            # (与 base_url 为空对齐: 宁可跳过, 不构造必然失败的空模型客户端)
            logger.warning(
                "未配置 LLM 模型名，已跳过 AI 功能。请在「系统设置」中填写模型名称。"
            )
            return None
        if not provider:
            provider = infer_provider(base_url)
        # P0 离线守卫: 远程 openai 兼容地址需用户显式确认风险 (Ollama 不受影响)
        if provider == "openai" and not is_local_url(base_url):
            acked = bool(settings.value("llm_allow_remote_ack", False))
            if not acked:
                self._llm_block_reason = "remote"
                logger.warning(
                    f"已阻止远程大模型连接 (财务数据不允许离开本机): {base_url}"
                )
                return None
            try:
                return create_llm_client(
                    provider=provider, base_url=base_url,
                    model=model, api_key=api_key,
                    allow_remote=True,
                )
            except ValueError as e:
                logger.error(f"LLM 配置无效: {e}")
                return None
        try:
            return create_llm_client(
                provider=provider, base_url=base_url,
                model=model, api_key=api_key,
            )
        except ValueError as e:
            logger.error(f"LLM 配置无效: {e}")
            return None

    def connect_drawer_signals(self) -> None:
        """防御式接线抽屉取消信号 (designer 契约: cancelRequested = Signal())。

        designer 并行重构 AgentDrawer, 用 getattr 拿到信号才连接,
        不依赖真实抽屉的具体实现; 幂等, 重复调用不会重复连接。
        """
        if self._drawer_cancel_connected:
            return
        drawer = getattr(self, "_agent_drawer", None)
        if drawer is None:
            return
        sig = getattr(drawer, "cancelRequested", None)
        if sig is None:
            return
        sig.connect(self._on_agent_cancel)
        self._drawer_cancel_connected = True

    def _on_agent_cancel(self) -> None:
        """用户点击"停止生成": 请求取消当前后台 LLM 任务 (幂等, 无任务时安全)。"""
        worker = getattr(self, "_active_worker", None)
        if worker is not None and hasattr(worker, "cancel"):
            worker.cancel()

    @staticmethod
    def _is_cancelled_error(message: str) -> bool:
        """判断后台错误是否由用户取消引起 (取消走安静路径)。"""
        return "已取消" in message

    def _finish_agent_error(self, message: str, prefix: str) -> None:
        """统一处理后台 LLM 失败 (P1 取消安静路径)。

        - 取消 ("已取消"): 气泡显示"已停止生成。", 不弹错误 InfoBar
        - 其他: 显示失败原因气泡并弹错误 InfoBar
        """
        if self._is_cancelled_error(message):
            self._agent_drawer.add_assistant_message("已停止生成。")
            return
        self._agent_drawer.add_assistant_message(
            f"{prefix}: {message}\n请检查大模型服务是否正常。"
        )
        self._show_llm_error_infobar(message)

    def _show_remote_blocked_infobar(self) -> None:
        """远程大模型连接被离线守卫拦截时给用户的警告提示 (P0)。"""
        InfoBar.warning(
            "已阻止远程大模型连接",
            "财务数据不允许离开本机。如确需使用云端服务，请在「系统设置」中显式开启并确认风险。",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self,
        )

    def _set_agent_busy(self, busy: bool) -> None:
        """LLM 后台任务执行期间禁用相关按钮, 避免重复触发; 结束后恢复。"""
        if busy:
            # 任何 LLM 流程启动前先确保取消信号已接线
            self.connect_drawer_signals()
        buttons: list[QPushButton] = []
        buttons.extend(self._import_page.findChildren(QPushButton, "DiagnoseBtn"))
        buttons.extend(self._import_page.findChildren(QPushButton, "DebateBtn"))
        send_btn = self._agent_drawer.findChild(QPushButton, "BtnPrimary")
        if send_btn is not None:
            buttons.append(send_btn)
        for btn in buttons:
            btn.setEnabled(not busy)
        # 抽屉输入区上方显示/隐藏 "AI 正在分析…" 弱提示
        self._agent_drawer.set_busy(busy)

    def _show_llm_error_infobar(self, message: str) -> None:
        """以中文 InfoBar 提示后台 LLM 任务异常。"""
        InfoBar.error(
            "AI 分析失败",
            f"大模型服务调用失败，请检查服务地址与网络后重试。\n{message}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self,
        )

    def _diagnose_rule(self, rule_id: str) -> None:
        """查找指定规则的失败结果并运行诊断引擎（可选 LLM 增强, 后台线程）。"""
        summary = self._state.results
        if summary is None:
            self._agent_drawer.add_assistant_message(
                "当前没有校验结果，无法进行诊断。请先执行校验后再尝试。"
            )
            return

        # 查找匹配的失败结果
        failed = [
            r for r in summary.results
            if r.rule_id == rule_id and not r.passed
        ]
        if not failed:
            # 可能该规则通过了，或未执行
            passed = [r for r in summary.results if r.rule_id == rule_id]
            if passed:
                self._agent_drawer.add_assistant_message(
                    f"规则 {rule_id} 已通过校验，无需诊断。"
                )
            else:
                self._agent_drawer.add_assistant_message(
                    f"未找到规则 {rule_id} 的校验结果，请确认该规则已执行。"
                )
            return

        self._agent_drawer.add_assistant_message(
            f"正在诊断规则 {rule_id} 的差异原因...\n请稍候。"
        )
        self._set_agent_busy(True)
        client = self._get_llm_client()
        if client is None and self._llm_block_reason == "remote":
            self._show_remote_blocked_infobar()

        def run_diagnose() -> str:
            engine = DiagnosisEngine()
            # 免责标注已由 diagnose_with_client/diagnose 自带, 此处不再拼接
            if client is not None:
                return engine.diagnose_with_client(failed[0], client)
            return engine.diagnose(failed[0])

        def on_success(text: str) -> None:
            self._agent_drawer.add_assistant_message(text)

        def on_error(message: str) -> None:
            logger.error(f"AI 诊断失败: {message}")
            self._finish_agent_error(message, "AI 诊断失败")

        worker = AgentWorker(
            run_diagnose, on_success, on_error, on_finished=lambda: self._set_agent_busy(False)
        )
        self._active_worker = worker
        worker.start()

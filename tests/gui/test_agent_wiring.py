"""GUI 接线测试: 离线守卫 / 取消信号 / 取消安静路径 / 辩论阶段提示 / 远程开关。

用 stub (QObject/QWidget + Signal、fake worker) 代替真实 AgentDrawer,
不依赖 designer 并行重构进度。
"""

from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import QWidget
from qfluentwidgets import SwitchButton

from fsa.agent.debate import DebateResult
from fsa.core.models.rule import Severity
from fsa.gui.main_window import MainWindow
from tests.gui.helpers import make_result, make_summary


class StubDrawer(QWidget):
    """模拟 AgentDrawer: 含契约信号/方法 (designer 并行实现)。"""

    cancelRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []
        self.stage_hints: list[str] = []
        self.suggestions: list[str] = []

    def set_stage_hint(self, text: str) -> None:
        self.stage_hints.append(text)

    def add_assistant_message(self, text: str) -> None:
        self.messages.append(text)

    def add_user_message(self, text: str) -> None:
        self.messages.append(text)

    def set_context(self, rule_id: str, rule_name: str) -> None:
        return None

    def set_busy(self, busy: bool) -> None:
        return None

    def set_suggestions(self, suggestions: list[str]) -> None:
        self.suggestions = suggestions


class FakeWorker:
    """模拟 AgentWorker: 只记录 cancel 调用。"""

    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


class FakeClient:
    """模拟 LLMClient (协议最小实现)。"""

    base_url = "http://localhost:8000/v1"
    model = "m"

    def __init__(self, base_url: str = "http://localhost:8000/v1") -> None:
        self.base_url = base_url

    def is_available(self) -> bool:
        return True

    def chat(self, messages, tools=None, timeout=None, cancel_event=None):
        from fsa.agent.llm_client import ChatMessage
        return ChatMessage(role="assistant", content="ok")

    def chat_stream(
        self, messages, tools=None, timeout=None,
        on_chunk=None, on_reasoning_chunk=None, cancel_event=None,
    ):
        return self.chat(messages, tools=tools, timeout=timeout)


def _make_window(qapp, qtbot, app_state) -> MainWindow:
    window = MainWindow(app_state, initial_dark=False, theme_mode="light")
    qtbot.addWidget(window)
    app_state.load_registry()
    return window


class TestRemoteGuardWiring:
    """P0 离线守卫接线: 远程地址拦截 / ack 放行 / 本地放行。"""

    def test_remote_without_ack_blocked(self, qapp, qtbot, app_state) -> None:
        window = _make_window(qapp, qtbot, app_state)
        settings = QSettings("FSA", "FinancialAudit")
        settings.setValue("llm_provider", "openai")
        settings.setValue("llm_base_url", "https://api.example.com/v1")
        settings.setValue("llm_model", "m")
        assert not settings.contains("llm_allow_remote_ack")
        client = window._get_llm_client()
        assert client is None
        assert window._llm_block_reason == "remote"

    def test_remote_with_ack_allowed(self, qapp, qtbot, app_state) -> None:
        window = _make_window(qapp, qtbot, app_state)
        settings = QSettings("FSA", "FinancialAudit")
        settings.setValue("llm_provider", "openai")
        settings.setValue("llm_base_url", "https://api.example.com/v1")
        settings.setValue("llm_model", "m")
        settings.setValue("llm_allow_remote_ack", True)
        client = window._get_llm_client()
        assert client is not None
        assert client.base_url == "https://api.example.com/v1"
        assert window._llm_block_reason == ""

    def test_local_openai_not_blocked(self, qapp, qtbot, app_state) -> None:
        window = _make_window(qapp, qtbot, app_state)
        settings = QSettings("FSA", "FinancialAudit")
        settings.setValue("llm_provider", "openai")
        settings.setValue("llm_base_url", "http://127.0.0.1:8000/v1")
        settings.setValue("llm_model", "m")
        client = window._get_llm_client()
        assert client is not None
        assert window._llm_block_reason == ""

    def test_unconfigured_not_blocked(self, qapp, qtbot, app_state) -> None:
        window = _make_window(qapp, qtbot, app_state)
        settings = QSettings("FSA", "FinancialAudit")
        settings.setValue("llm_provider", "openai")
        settings.setValue("llm_base_url", "")
        settings.setValue("llm_model", "m")
        client = window._get_llm_client()
        assert client is None
        assert window._llm_block_reason == ""


class TestCancelWiring:
    """P1 取消接线: 抽屉取消信号 -> worker.cancel (幂等)。"""

    def test_cancel_signal_triggers_worker_cancel(self, qapp, qtbot, app_state) -> None:
        window = _make_window(qapp, qtbot, app_state)
        stub = StubDrawer()
        window._agent_drawer = stub
        window.connect_drawer_signals()
        worker = FakeWorker()
        window._active_worker = worker
        stub.cancelRequested.emit()
        assert worker.cancelled

    def test_cancel_without_worker_is_safe(self, qapp, qtbot, app_state) -> None:
        window = _make_window(qapp, qtbot, app_state)
        stub = StubDrawer()
        window._agent_drawer = stub
        window._active_worker = None
        window.connect_drawer_signals()
        stub.cancelRequested.emit()  # 无 worker 不崩溃

    def test_connect_drawer_signals_idempotent(self, qapp, qtbot, app_state) -> None:
        window = _make_window(qapp, qtbot, app_state)
        stub = StubDrawer()
        window._agent_drawer = stub
        window.connect_drawer_signals()
        window.connect_drawer_signals()  # 重复连接不应导致重复触发
        worker = FakeWorker()
        window._active_worker = worker
        stub.cancelRequested.emit()
        assert worker.cancelled is True


class TestCancelQuietPath:
    """P1 取消安静路径: "已取消" 气泡"已停止生成。" 且不弹错误 InfoBar。"""

    def test_is_cancelled_error(self, qapp, qtbot, app_state) -> None:
        window = _make_window(qapp, qtbot, app_state)
        assert window._is_cancelled_error("LLMError: 已取消") is True
        assert window._is_cancelled_error("LLMError: 连接超时") is False

    def test_cancelled_error_quiet_path(self, qapp, qtbot, app_state) -> None:
        window = _make_window(qapp, qtbot, app_state)
        stub = StubDrawer()
        window._agent_drawer = stub
        window._show_llm_error_infobar = MagicMock()  # type: ignore[method-assign]
        window._finish_agent_error("LLMError: 已取消", "AI 诊断失败")
        assert stub.messages == ["已停止生成。"]
        window._show_llm_error_infobar.assert_not_called()

    def test_error_path_shows_infobar(self, qapp, qtbot, app_state) -> None:
        window = _make_window(qapp, qtbot, app_state)
        stub = StubDrawer()
        window._agent_drawer = stub
        window._show_llm_error_infobar = MagicMock()  # type: ignore[method-assign]
        window._finish_agent_error("连接失败", "AI 诊断失败")
        assert stub.messages == ["AI 诊断失败: 连接失败\n请检查大模型服务是否正常。"]
        window._show_llm_error_infobar.assert_called_once_with("连接失败")


class TestDebateStageHint:
    """P2 辩论阶段提示: DebateEngine.on_stage -> drawer.set_stage_hint。"""

    def test_debate_on_stage_calls_set_stage_hint(
        self, qapp, qtbot, app_state, monkeypatch
    ) -> None:
        window = _make_window(qapp, qtbot, app_state)
        stub = StubDrawer()
        window._agent_drawer = stub
        window._open_drawer = lambda: None  # type: ignore[method-assign]

        results = [
            make_result(
                "A-001", passed=False, diff=5.0,
                severity=Severity.ERROR, category="A-表内平衡",
            ),
        ]
        app_state.set_results(make_summary(results), persist=False)

        # 假客户端 + 假 DebateEngine (捕获 on_stage 并按序触发)
        captured: dict = {}
        fake_client = FakeClient()
        window._get_llm_client = lambda: fake_client  # type: ignore[method-assign]
        window._llm_available = lambda _c: True  # type: ignore[method-assign]

        class FakeDebateEngine:
            def __init__(self, analyst, critic, judge) -> None:
                return None

            def debate(self, case_data: str, on_stage=None):
                captured["on_stage"] = on_stage
                for hint in ("分析师正在分析…", "反方审计师正在质疑…", "裁判正在出具结论…"):
                    if on_stage is not None:
                        on_stage(hint)
                return DebateResult(
                    analyst_view="分析师观点",
                    critic_view="反方质疑",
                    final_verdict="最终结论",
                    confidence="高",
                )

        monkeypatch.setattr("fsa.agent.debate.DebateEngine", FakeDebateEngine)

        window._on_debate("A-001")
        qtbot.waitUntil(lambda: len(stub.messages) >= 1, timeout=5000)
        assert captured["on_stage"] is not None
        assert stub.stage_hints == [
            "分析师正在分析…",
            "反方审计师正在质疑…",
            "裁判正在出具结论…",
        ]


class TestRemoteSwitchSettings:
    """P0 设置页远程开关: 关闭移除 ack 键; 分区构建出开关。"""

    def test_toggle_off_removes_ack(self, qapp, qtbot) -> None:
        settings = QSettings("FSA", "FinancialAudit")
        settings.setValue("llm_allow_remote_ack", True)
        from fsa.gui.pages.settings_sections import _on_llm_remote_toggled

        switch = SwitchButton()
        _on_llm_remote_toggled(False, switch, settings, None)
        assert not settings.contains("llm_allow_remote_ack")

    def test_build_llm_section_creates_remote_switch(
        self, qapp, qtbot, app_state
    ) -> None:
        class FakeSettingsPage(QWidget):
            def _save_llm_provider(self) -> None:
                return None

            def _save_llm_config(self) -> None:
                return None

        from fsa.gui.pages.settings_sections import build_llm_section

        page = FakeSettingsPage()
        settings = QSettings("FSA", "FinancialAudit")
        frame = build_llm_section(page, settings, app_state)
        assert frame is not None
        switch = getattr(page, "_llm_remote_switch", None)
        assert switch is not None
        assert isinstance(switch, SwitchButton)
        assert switch.isChecked() is False  # 默认关

"""AgentWorker 后台 LLM 任务与主窗口 LLM 集成测试 (P0 主线程冻结修复)。

覆盖:
- AgentWorker 后台执行并将结果回传主线程 (成功/失败/结束回调)
- 主窗口 _set_agent_busy 执行期间禁用 AI 按钮
- _get_ollama_client 独立分支已移除, 统一走 _get_llm_client (QSettings 唯一配置源)
"""

from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QPushButton

from fsa.core.models.rule import Severity
from fsa.gui.agent_worker import AgentWorker
from fsa.gui.main_window import MainWindow
from fsa.gui.widgets.result_card import ResultCard
from tests.gui.helpers import make_result, make_summary


class TestAgentWorker:
    """AgentWorker 后台任务回传测试。"""

    def test_success_delivered_to_ui_thread(self, qapp, qtbot) -> None:
        """任务成功结果回传主线程。"""
        received: list[str] = []

        def on_success(value: str) -> None:
            received.append(value)

        worker = AgentWorker(
            target=lambda: "后台结果",
            on_success=on_success,
            on_error=lambda _m: received.append("ERR"),
        )
        worker.start()
        qtbot.waitUntil(lambda: received == ["后台结果"], timeout=5000)

    def test_error_delivered_to_ui_thread(self, qapp, qtbot) -> None:
        """任务异常以错误消息回传主线程。"""
        received: list[str] = []

        def boom() -> str:
            raise ValueError("模拟后台异常")

        worker = AgentWorker(
            target=boom,
            on_success=lambda _v: received.append("OK"),
            on_error=lambda message: received.append(message),
        )
        worker.start()
        qtbot.waitUntil(lambda: len(received) == 1, timeout=5000)
        assert "模拟后台异常" in received[0]

    def test_finished_callback_called(self, qapp, qtbot) -> None:
        """任务结束后 on_finished 被调用 (用于恢复 UI 状态)。"""
        finished: list[int] = []

        worker = AgentWorker(
            target=lambda: "x",
            on_success=lambda _v: None,
            on_error=lambda _m: None,
            on_finished=lambda: finished.append(1),
        )
        worker.start()
        qtbot.waitUntil(lambda: len(finished) == 1, timeout=5000)

    def test_runs_in_background_thread(self, qapp, qtbot) -> None:
        """任务运行在非主线程, 不阻塞 UI。"""
        import threading

        main_thread = threading.get_ident()
        thread_ids: list[int] = []

        def target() -> str:
            thread_ids.append(threading.get_ident())
            return "ok"

        worker = AgentWorker(
            target=target,
            on_success=lambda _v: None,
            on_error=lambda _m: None,
        )
        worker.start()
        qtbot.waitUntil(lambda: len(thread_ids) == 1, timeout=5000)
        assert thread_ids[0] != main_thread


class TestAgentWorkerCancel:
    """P1 取消机制: AgentWorker.cancel 幂等, 取消事件后台可观察。"""

    def _make_worker(self) -> AgentWorker:
        return AgentWorker(
            target=lambda: "ok",
            on_success=lambda _v: None,
            on_error=lambda _m: None,
        )

    def test_cancel_sets_event(self, qapp, qtbot) -> None:
        worker = self._make_worker()
        assert not worker.cancel_event.is_set()
        worker.cancel()
        assert worker.cancel_event.is_set()

    def test_cancel_is_idempotent(self, qapp, qtbot) -> None:
        worker = self._make_worker()
        worker.cancel()
        worker.cancel()  # 幂等: 重复调用不抛异常
        assert worker.cancel_event.is_set()

    def test_cancel_event_readonly_property(self, qapp, qtbot) -> None:
        worker = self._make_worker()
        assert worker.cancel_event is worker.cancel_event

    def test_background_target_observes_cancel_event(self, qapp, qtbot) -> None:
        """后台任务线程中可读取 cancel_event 取消状态。"""
        seen: list[bool] = []

        def target() -> str:
            seen.append(worker.cancel_event.is_set())
            return "ok"

        worker = AgentWorker(
            target=target,
            on_success=lambda _v: None,
            on_error=lambda _m: None,
        )
        worker.cancel()
        worker.start()
        qtbot.waitUntil(lambda: len(seen) == 1, timeout=5000)
        assert seen[0] is True

    def test_cancelled_llm_error_delivered_to_on_error(self, qapp, qtbot) -> None:
        """后台任务抛 LLMError("已取消") 经 on_error 回传主线程。"""
        from fsa.agent.llm_client import LLMError

        received: list[str] = []

        def cancelled_task() -> str:
            raise LLMError("已取消")

        worker = AgentWorker(
            target=cancelled_task,
            on_success=lambda _v: received.append("OK"),
            on_error=lambda message: received.append(message),
        )
        worker.start()
        qtbot.waitUntil(lambda: len(received) == 1, timeout=5000)
        assert "已取消" in received[0]


class TestAgentWorkerStreamChunks:
    """流式分块经 QMetaObject 回传主线程 (P1)。"""

    def test_content_chunk_delivered_to_main_thread(self, qapp, qtbot) -> None:
        """emit_chunk 分块在主线程回调 on_chunk。"""
        received: list[str] = []

        def on_chunk(text: str) -> None:
            received.append(text)

        worker = AgentWorker(
            target=lambda: "ok",
            on_success=lambda _v: None,
            on_error=lambda _m: None,
            on_chunk=on_chunk,
        )
        worker.emit_chunk("分块1")
        worker.emit_chunk("分块2")
        qtbot.waitUntil(lambda: len(received) == 2, timeout=5000)
        assert received == ["分块1", "分块2"]

    def test_reasoning_chunk_delivered_to_main_thread(self, qapp, qtbot) -> None:
        """emit_reasoning_chunk 分块在主线程回调 on_reasoning_chunk。"""
        received: list[str] = []

        def on_reasoning(text: str) -> None:
            received.append(text)

        worker = AgentWorker(
            target=lambda: "ok",
            on_success=lambda _v: None,
            on_error=lambda _m: None,
            on_reasoning_chunk=on_reasoning,
        )
        worker.emit_reasoning_chunk("推理")
        qtbot.waitUntil(lambda: received == ["推理"], timeout=5000)

    def test_stream_worker_with_ask_stream_end_to_end(self, qapp, qtbot, app_state) -> None:
        """后台 ask_stream 产生的分块经 worker 回传主线程。"""
        from fsa.agent.agent_loop import AgentLoop
        from fsa.agent.llm_client import ChatMessage

        class StreamingLLM:
            base_url = "http://fake"
            model = "m"

            def is_available(self) -> bool:
                return True

            def chat(self, messages, tools=None, timeout=None):
                return ChatMessage(role="assistant", content="完整回答")

            def chat_stream(
                self,
                messages,
                tools=None,
                timeout=None,
                on_chunk=None,
                on_reasoning_chunk=None,
            ):
                if on_chunk is not None:
                    on_chunk("逐字")
                    on_chunk("内容")
                return ChatMessage(role="assistant", content="逐字内容")

        chunks: list[str] = []

        def run() -> str:
            loop = AgentLoop(StreamingLLM(), app_state)
            return loop.ask_stream("你好", on_chunk=lambda c: worker.emit_chunk(c))

        def on_chunk(text: str) -> None:
            chunks.append(text)

        worker = AgentWorker(run, on_success=lambda _v: None, on_error=lambda _m: None, on_chunk=on_chunk)
        worker.start()
        # 正常结束前最后一个分块为 DISCLAIMER_TEXT 免责标注
        qtbot.waitUntil(lambda: len(chunks) == 3, timeout=5000)
        assert chunks[:2] == ["逐字", "内容"]
        assert (
            chunks[2]
            == "\n\n" + "⚠️ 以上内容由 AI 模型生成，仅供参考，不构成审计意见；最终判断请以规则引擎结果与人工复核为准。"
        )


class TestAgentBusyState:
    """执行期间对应按钮禁用并显示加载态 (P0)。"""

    def _setup_window(self, qapp, qtbot, app_state) -> MainWindow:
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        app_state.load_registry()
        results = [
            make_result(
                "A-001",
                passed=False,
                diff=5.0,
                severity=Severity.ERROR,
                category="A-表内平衡",
            ),
        ]
        app_state.set_results(make_summary(results), persist=False)
        return window

    def test_set_agent_busy_disables_and_restores_buttons(self, qapp, qtbot, app_state) -> None:
        """busy=True 禁用 AI 按钮, busy=False 恢复。"""
        window = self._setup_window(qapp, qtbot, app_state)
        card = window._import_page.findChildren(ResultCard)[0]
        diag_btn = card.findChild(QPushButton, "DiagnoseBtn")
        debate_btn = card.findChild(QPushButton, "DebateBtn")
        assert diag_btn is not None and debate_btn is not None

        window._set_agent_busy(True)
        assert not diag_btn.isEnabled()
        assert not debate_btn.isEnabled()

        window._set_agent_busy(False)
        assert diag_btn.isEnabled()
        assert debate_btn.isEnabled()


class TestUnifiedLlmClient:
    """统一 LLM 客户端分支 (P1#9): 无独立 Ollama 分支, QSettings 唯一配置源。"""

    def test_get_ollama_client_removed(self, qapp, qtbot, app_state) -> None:
        """_get_ollama_client 独立分支已删除。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        assert not hasattr(window, "_get_ollama_client")
        assert not hasattr(window, "_ollama_available")

    def test_get_llm_client_none_when_unconfigured(self, qapp, qtbot, app_state) -> None:
        """未配置 LLM 时返回 None。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        settings = QSettings("FSA", "FinancialAudit")
        settings.setValue("llm_provider", "")
        settings.setValue("llm_base_url", "")
        assert window._get_llm_client() is None

    def test_get_llm_client_none_when_base_url_empty(self, qapp, qtbot, app_state) -> None:
        """选择了 provider 但服务地址为空时返回 None (A6-002 空值跳过)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        settings = QSettings("FSA", "FinancialAudit")
        settings.setValue("llm_provider", "ollama")
        settings.setValue("llm_base_url", "")
        assert window._get_llm_client() is None

    def test_get_llm_client_from_settings(self, qapp, qtbot, app_state) -> None:
        """从 QSettings 配置构建客户端 (openai 兼容)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        settings = QSettings("FSA", "FinancialAudit")
        settings.setValue("llm_provider", "openai")
        # 本机地址: P0 离线守卫默认阻止远程 openai 连接, 本地地址正常放行
        settings.setValue("llm_base_url", "http://127.0.0.1:8000/v1")
        settings.setValue("llm_model", "test-model")
        client = window._get_llm_client()
        assert client is not None
        assert client.base_url == "http://127.0.0.1:8000/v1"
        assert client.model == "test-model"

    def test_llm_available_cache_invalidated_by_config_change(self, qapp, qtbot, app_state) -> None:
        """可用性缓存按 base_url|model 键控, 配置切换后重新探测。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        class FakeClient:
            def __init__(self, url: str) -> None:
                self.base_url = url
                self.model = "m"
                self.checks = 0

            def is_available(self) -> bool:
                self.checks += 1
                return True

            def chat(self, messages, tools=None, timeout=None):
                from fsa.agent.llm_client import ChatMessage

                return ChatMessage(role="assistant", content="ok")

            def chat_stream(
                self,
                messages,
                tools=None,
                timeout=None,
                on_chunk=None,
                on_reasoning_chunk=None,
            ):
                return self.chat(messages, tools=tools, timeout=timeout)

        c1 = FakeClient("http://a")
        assert window._llm_available(c1) is True
        assert window._llm_available(c1) is True
        assert c1.checks == 1  # 命中缓存

        c2 = FakeClient("http://b")
        assert window._llm_available(c2) is True
        assert c2.checks == 1  # 新配置 -> 重新探测 (缓存失效)

    def test_llm_available_ttl_expiry_reprobes(self, qapp, qtbot, app_state, monkeypatch) -> None:
        """可用性缓存带 TTL: 60 秒内不重探测, 过期后重新探测 (P1-3)。"""
        import fsa.gui.main_window_agent as mwa

        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        now = [100.0]
        monkeypatch.setattr(mwa.time, "monotonic", lambda: now[0])

        class FakeClient:
            def __init__(self) -> None:
                self.base_url = "http://a"
                self.model = "m"
                self.checks = 0

            def is_available(self) -> bool:
                self.checks += 1
                return False

            def chat(self, messages, tools=None, timeout=None):
                from fsa.agent.llm_client import ChatMessage

                return ChatMessage(role="assistant", content="ok")

            def chat_stream(
                self,
                messages,
                tools=None,
                timeout=None,
                on_chunk=None,
                on_reasoning_chunk=None,
            ):
                return self.chat(messages, tools=tools, timeout=timeout)

        client = FakeClient()
        assert window._llm_available(client) is False
        assert client.checks == 1  # 首次探测

        # TTL 内第二次调用命中缓存, 不重新探测
        assert window._llm_available(client) is False
        assert client.checks == 1

        # TTL 过期后重新探测 (服务恢复后不再永久缓存不可用)
        now[0] += mwa._LLM_AVAILABILITY_TTL_SECONDS + 1
        assert window._llm_available(client) is False
        assert client.checks == 2

    def test_get_llm_client_none_when_model_empty(self, qapp, qtbot, app_state) -> None:
        """配置了服务地址但模型名为空时返回 None (P1-4, 与 base_url 为空对齐)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        settings = QSettings("FSA", "FinancialAudit")
        settings.setValue("llm_provider", "openai")
        settings.setValue("llm_base_url", "http://10.0.0.5:8000/v1")
        settings.setValue("llm_model", "")
        assert window._get_llm_client() is None


class TestTraceLocationFormat:
    """追溯位置格式化 (D-01): PDF 来源解码为「第X页表内第N行」。"""

    def test_pdf_row_decoded(self) -> None:
        from fsa.gui.main_window import _format_trace_loc

        # 页码 2, 表内行 5
        assert _format_trace_loc(20_000_005, "") == "第2页表内第5行"

    def test_excel_row_unchanged(self) -> None:
        from fsa.gui.main_window import _format_trace_loc

        assert _format_trace_loc(35, "期末余额") == "第35行 期末余额列"

    def test_row_zero_shows_column(self) -> None:
        from fsa.gui.main_window import _format_trace_loc

        assert _format_trace_loc(0, "未在报表中找到（按 0 处理）") == "未在报表中找到（按 0 处理）"
        assert _format_trace_loc(0, "") == "位置未知"


class TestHistoryGetById:
    """历史记录按 id 直查 (B-16): 不再线性扫描 get_recent。"""

    def test_view_history_uses_get_by_id(self, qapp, qtbot, app_state) -> None:
        """_on_view_history 调用 repo.get_by_id 而非 get_recent 线性扫描。"""
        calls: list[str] = []

        class FakeRepo:
            def get_by_id(self, history_id: int):
                calls.append("get_by_id")
                return None

            def get_recent(self, limit: int = 50):
                calls.append("get_recent")
                return []

            def get_detail(self, history_id: int):
                return []

        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        app_state._history_repo = FakeRepo()
        window._on_view_history(999)
        assert "get_by_id" in calls
        assert "get_recent" not in calls


class TestAgentBusyHint:
    """LLM 等待弱提示 (C5-3): busy 期间显示"AI 正在分析…"。"""

    def test_busy_hint_shown_and_hidden(self, qapp, qtbot, app_state) -> None:
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        # 父容器未显示时 isVisible() 恒为 False, 用 isHidden() 断言显隐状态
        window._set_agent_busy(True)
        assert not window._agent_drawer._busy_hint.isHidden()
        window._set_agent_busy(False)
        assert window._agent_drawer._busy_hint.isHidden()

    def test_cancelled_worker_drops_late_chunks(self, qapp, qtbot) -> None:
        """用户停止后, 已排队但未投递的分块不再渲染。"""
        received: list[str] = []

        worker = AgentWorker(
            target=lambda: "ok",
            on_success=lambda _v: None,
            on_error=lambda _m: None,
            on_chunk=received.append,
            on_reasoning_chunk=received.append,
        )
        worker.cancel()
        worker.emit_chunk("迟到分块")
        worker.emit_reasoning_chunk("迟到推理")
        qtbot.wait(100)
        assert received == []

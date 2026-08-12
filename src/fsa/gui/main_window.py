"""主窗口: QMainWindow + 自定义侧边栏 + 顶栏 + AI 抽屉。

替代 FluentWindow, 完全匹配 Demo v4 设计:
- 左侧 240px 自定义侧边栏 (logo + 导航 + 底部版本)
- 顶部 48px 半透明顶栏 (标题 + 副标题 + 操作按钮)
- 中间内容区 (QStackedWidget 切换页面)
- 右下角 AI 浮动按钮
- 右侧 AI 抽屉 (可拖拽缩放 + 遮罩点击收起)
"""

from __future__ import annotations

from datetime import datetime

from loguru import logger
from PySide6.QtCore import QEvent, QSettings, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import InfoBar, InfoBarPosition

from fsa.agent.diagnosis import DiagnosisEngine
from fsa.agent.ollama_client import OllamaClient
from fsa.core.exporter.audit_exporter import AuditExporter
from fsa.gui.app_state import AppState
from fsa.gui.pages.audit_page import AuditPage
from fsa.gui.pages.history_page import HistoryPage
from fsa.gui.pages.import_page import ImportPage
from fsa.gui.pages.rule_page import RulePage
from fsa.gui.pages.settings_page import SettingsPage
from fsa.gui.theme import apply_theme, get_qss, notify_theme_listeners
from fsa.gui.widgets.agent_drawer import AgentDrawer
from fsa.gui.widgets.agent_fab import AgentFAB
from fsa.gui.widgets.sidebar import Sidebar
from fsa.gui.widgets.topbar import Topbar

# 页面 ID 到标题/副标题的映射
_PAGE_TITLES: dict[str, tuple[str, str]] = {
    "navImport": ("数据导入与校验", "准备导入报表"),
    "navAudit": ("审计底稿", "校验结果审计底稿"),
    "navRules": ("规则管理", "勾稽校验规则库"),
    "navHistory": ("历史记录", "校验历史记录"),
    "navSettings": ("系统设置", "系统参数配置"),
}


class MainWindow(QMainWindow):
    """主窗口: 侧边栏 + 顶栏 + 内容区 + AI 抽屉。

    快捷键:
        Ctrl+D - 切换深色/亮色主题
        ESC - 关闭 AI 抽屉
    """

    def __init__(
        self,
        state: AppState,
        initial_dark: bool = False,
        theme_mode: str = "light",
    ) -> None:
        super().__init__()
        self.setObjectName("MainWindow")
        self._state = state
        self._dark = initial_dark
        self._theme_mode = theme_mode

        self.setWindowTitle("财务报表勾稽校验系统")
        self._set_window_icon()
        self.resize(1280, 800)
        self.setMinimumSize(960, 600)

        self._setup_ui()
        self._connect_signals()
        self._setup_shortcuts()

    def _set_window_icon(self) -> None:
        """设置窗口/任务栏图标 (resources/logo_256.png)。"""
        from PySide6.QtGui import QIcon

        from fsa.core.resources import resource_path

        icon_path = resource_path("resources/logo_256.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 侧边栏
        self._sidebar = Sidebar()
        root.addWidget(self._sidebar)

        # 主区域
        main_area = QFrame()
        main_area.setObjectName("MainArea")
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 顶栏
        self._topbar = Topbar()
        main_layout.addWidget(self._topbar)

        # 内容区 (QStackedWidget)
        self._stack = QStackedWidget()
        self._import_page = ImportPage(self._state)
        self._audit_page = AuditPage(self._state)
        self._rule_page = RulePage(self._state)
        self._history_page = HistoryPage(self._state)
        self._settings_page = SettingsPage(self._state)

        self._stack.addWidget(self._import_page)
        self._stack.addWidget(self._audit_page)
        self._stack.addWidget(self._rule_page)
        self._stack.addWidget(self._history_page)
        self._stack.addWidget(self._settings_page)

        main_layout.addWidget(self._stack, stretch=1)

        root.addWidget(main_area, stretch=1)

        # AI 浮动按钮 (覆盖在主区域上)
        self._agent_fab = AgentFAB(self)
        self._agent_fab.raise_()

        # AI 抽屉 (默认隐藏)
        self._agent_drawer = AgentDrawer(self._state.chat_repo, self)
        self._agent_drawer.hide()

        # 遮罩层 (点击收起抽屉)
        self._overlay = QFrame(self)
        self._overlay.setObjectName("AgentOverlay")
        self._overlay.setStyleSheet("background-color: rgba(0,0,0,0.2);")
        self._overlay.hide()
        self._overlay.installEventFilter(self)

        # FAB 定位到右下角 (demo: bottom 24px right 24px)
        self._position_fab()
        # Ollama 客户端（延迟初始化）
        self._ollama: OllamaClient | None = None
        # 可用性缓存（None=未检查, True=可用, False=不可用）
        self._ollama_available: bool | None = None

    def _connect_signals(self) -> None:
        # 侧边栏导航
        self._sidebar.nav_changed.connect(self._on_nav)

        # 顶栏按钮
        self._topbar.theme_clicked.connect(self._toggle_theme)
        self._topbar.reset_clicked.connect(self._on_reset)
        self._topbar.validate_clicked.connect(self._import_page.trigger_validate)
        self._topbar.export_clicked.connect(self._on_export)

        # 校验完成后启用导出按钮
        self._state.results_changed.connect(self._on_results_ready)

        # AI 按钮
        self._agent_fab.clicked_fab.connect(self._toggle_drawer)
        self._agent_drawer.close_requested.connect(self._close_drawer)
        self._agent_drawer.send_requested.connect(self._on_agent_send)

        # 导入页面状态
        self._import_page.validate_enabled_changed.connect(
            self._topbar.set_validate_enabled
        )
        self._import_page.diagnose_requested.connect(self._on_diagnose)
        self._import_page.debate_requested.connect(self._on_debate)

        # 历史页面: 查看历史记录
        self._history_page.view_requested.connect(self._on_view_history)

        # 设置页主题变更
        self._settings_page.theme_changed.connect(self._on_settings_theme_changed)

    def _setup_shortcuts(self) -> None:
        ctrl_d = QShortcut(QKeySequence("Ctrl+D"), self)
        ctrl_d.activated.connect(self._toggle_theme)

    # ── 导航 ──

    def _on_nav(self, nav_id: str) -> None:
        page_map = {
            "navImport": 0,
            "navAudit": 1,
            "navRules": 2,
            "navHistory": 3,
            "navSettings": 4,
        }
        idx = page_map.get(nav_id, 0)
        self._stack.setCurrentIndex(idx)
        self._current_nav = nav_id

        title, subtitle = _PAGE_TITLES.get(nav_id, ("", ""))
        self._topbar.set_title(title, subtitle)

        # AI 助手 FAB 仅在"工作区"页面显示 (数据导入 + 审计底稿)
        workspace = nav_id in ("navImport", "navAudit")
        self._agent_fab.setVisible(workspace and not self._agent_drawer.isVisible())
        if not workspace and self._agent_drawer.isVisible():
            self._close_drawer()

    def _get_current_nav(self) -> str:
        """返回当前导航页 ID。"""
        return getattr(self, "_current_nav", "navImport")

    # ── 主题 ──

    def _toggle_theme(self) -> None:
        self._dark = not self._dark
        self._theme_mode = "dark" if self._dark else "light"
        apply_theme(dark=self._dark)
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyleSheet(get_qss(self._dark))
        notify_theme_listeners()
        self._topbar.set_theme_icon(self._dark)
        # 保存用户显式选择
        settings = QSettings("FSA", "FinancialAudit")
        settings.setValue("theme_mode", self._theme_mode)

    def _on_settings_theme_changed(self, dark: bool) -> None:
        """设置页切换主题时同步主窗口状态。"""
        self._dark = dark
        self._topbar.set_theme_icon(dark)

    # ── 重置 ──

    def _on_reset(self) -> None:
        self._state.clear_all()
        self._topbar.set_export_enabled(False)
        self._topbar.set_validate_enabled(False)
        self._sidebar.set_active_nav("navImport")
        self._on_nav("navImport")
        self._agent_fab.set_badge(False)
        InfoBar.success(
            "已重置",
            "已清空所有报表和校验结果",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self,
        )

    # ── 导出 ──

    def _on_export(self) -> None:
        summary = self._state.results
        if summary is None:
            InfoBar.warning(
                "提示",
                "请先执行校验，再导出底稿",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        period = summary.period or "未命名"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"审计底稿_{period}_{timestamp}.xlsx"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出审计底稿",
            default_name,
            "Excel 文件 (*.xlsx)",
        )
        if not path:
            return

        try:
            exporter = AuditExporter()
            exporter.export(summary, path)
            InfoBar.success(
                "导出成功",
                f"已导出到 {path}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self,
            )
        except PermissionError:
            InfoBar.error(
                "导出失败",
                "文件被占用，请关闭已打开的 Excel 文件后重试",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self,
            )
        except OSError:
            InfoBar.error(
                "导出失败",
                "无法写入文件，请检查路径权限",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self,
            )

    # ── AI 抽屉 ──

    def _toggle_drawer(self) -> None:
        if self._agent_drawer.isVisible():
            self._close_drawer()
        else:
            self._open_drawer()

    def _open_drawer(self) -> None:
        self._overlay.show()
        self._overlay.raise_()
        self._agent_drawer.show()
        self._agent_drawer.raise_()
        self._position_drawer()
        self._agent_fab.set_badge(False)
        # 抽屉打开时隐藏 FAB, 避免遮盖抽屉底部的建议气泡/输入区
        self._agent_fab.hide()

    def _close_drawer(self) -> None:
        self._agent_drawer.hide()
        self._overlay.hide()
        # 抽屉关闭后恢复 FAB (仅在当前页是工作区时)
        current_nav = self._get_current_nav()
        if current_nav in ("navImport", "navAudit"):
            self._agent_fab.show()
            self._position_fab()

    def _position_drawer(self) -> None:
        """定位 AI 抽屉和遮罩层到右侧。"""
        drawer_width = self._agent_drawer.width()
        rect = self.centralWidget().geometry()
        x = rect.right() - drawer_width
        self._agent_drawer.setGeometry(
            x, rect.top(), drawer_width, rect.height()
        )
        self._overlay.setGeometry(rect.left(), rect.top(), rect.width() - drawer_width, rect.height())

    def _position_fab(self) -> None:
        """定位 AI 浮动按钮到右下角 (demo: bottom 24px, right 24px)。"""
        rect = self.centralWidget().geometry()
        fab_size = self._agent_fab.width()
        margin = 24
        self._agent_fab.move(
            rect.right() - fab_size - margin,
            rect.bottom() - fab_size - margin,
        )
        self._agent_fab.raise_()

    def _on_results_ready(self) -> None:
        """校验完成后启用导出按钮并显示 FAB 角标。"""
        summary = self._state.results
        self._topbar.set_export_enabled(summary is not None)
        self._update_suggestions()

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

    def _on_view_history(self, history_id: int) -> None:
        """加载历史校验记录并跳转到导入页展示 (不重复持久化)。"""
        repo = self._state.history_repo
        if repo is None:
            InfoBar.warning(
                "提示", "历史记录存储不可用",
                orient=Qt.Orientation.Horizontal, isClosable=True,
                position=InfoBarPosition.TOP, duration=3000, parent=self,
            )
            return

        try:
            record = next(
                (r for r in repo.get_recent(limit=200) if r["id"] == history_id),
                None,
            )
            if record is None:
                raise LookupError(f"历史记录 #{history_id} 不存在")
            results = repo.get_detail(history_id)
        except (LookupError, RuntimeError) as e:
            logger.error(f"加载历史记录失败: {e}")
            InfoBar.error(
                "加载失败", str(e),
                orient=Qt.Orientation.Horizontal, isClosable=True,
                position=InfoBarPosition.TOP, duration=3000, parent=self,
            )
            return

        from fsa.core.models.report import ReportType
        from fsa.core.models.result import ValidationSummary

        summary = ValidationSummary(
            period=record["period"] or "",
            total=record["total"],
            passed=record["passed"],
            failed=record["failed"],
            errored=record["errored"],
            skipped=record["skipped"],
            results=results,
            report_types=[ReportType(t) for t in record["report_types"]],
        )
        self._state.set_results(summary, persist=False)
        self._on_nav("navImport")
        # 注意: 不再弹 InfoBar —— 页面跳转+结果回填已是充分反馈,
        # 额外提示条会在用户后续点击筛选按钮时造成"弹窗闪现"的干扰
        if summary is not None:
            has_issues = summary.failed + summary.errored > 0
            self._agent_fab.set_badge(has_issues)

    def _on_agent_send(self, text: str) -> None:
        """处理用户发送的消息: 优先 AgentLoop (多轮+工具), 无 LLM 回退规则化。

        如果当前有规则上下文，则对该规则进行诊断分析；
        否则用 AgentLoop 进行多轮对话 + 工具调用;
        无 LLM 时给出通用的中文帮助提示。
        """
        logger.info(f"AI 助手收到消息: {text}")
        rule_id = self._agent_drawer.context_rule_id

        if rule_id is not None:
            self._diagnose_rule(rule_id)
            return

        # 尝试 AgentLoop (多轮对话 + 工具调用)
        client = self._get_llm_client()
        if client is not None and self._llm_available(client):
            self._run_agent_loop(client, text)
            return

        # 无 LLM: 智能规则化回退 (规则查询/知识库, 而非固定文本)
        from fsa.agent.fallback import fallback_answer
        self._agent_drawer.add_assistant_message(
            fallback_answer(text, self._state)
        )

    def _llm_available(self, client) -> bool:
        """检查 LLM 可用性 (缓存结果避免重复探测)。"""
        if self._ollama_available is None:
            try:
                self._ollama_available = bool(client.is_available())
            except Exception:
                self._ollama_available = False
        return bool(self._ollama_available)

    def _run_agent_loop(self, client, text: str) -> None:
        """运行 AgentLoop: 多轮对话 + 工具调用 + 分步推理。"""
        from fsa.agent.agent_loop import AgentLoop
        from fsa.agent.llm_client import LLMError

        history = self._agent_drawer.get_chat_history(limit=10)
        try:
            answer = AgentLoop(client, self._state).ask(text, history=history)
            self._agent_drawer.add_assistant_message(answer)
        except LLMError as e:
            logger.error(f"AgentLoop 失败: {e}")
            self._agent_drawer.add_assistant_message(
                f"AI 分析暂时不可用: {e}\n\n建议您检查大模型服务是否正常运行。"
            )

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

    def _get_ollama_client(self) -> OllamaClient:
        """延迟初始化 Ollama 客户端。"""
        if self._ollama is None:
            self._ollama = OllamaClient()
        return self._ollama

    def _get_llm_client(self):
        """根据设置构建 LLM 客户端 (provider 抽象)。

        从 QSettings 读取 llm_provider/llm_base_url/llm_model/llm_api_key。
        返回 LLMClient 或 None (未配置时)。
        """
        from fsa.agent.llm_client import create_llm_client

        settings = QSettings("FSA", "FinancialAudit")
        provider = str(settings.value("llm_provider", ""))
        if not provider:
            return None
        base_url = str(settings.value("llm_base_url", ""))
        model = str(settings.value("llm_model", "qwen2.5:7b"))
        api_key = str(settings.value("llm_api_key", ""))
        if not base_url:
            return None
        try:
            return create_llm_client(
                provider=provider, base_url=base_url,
                model=model, api_key=api_key,
            )
        except ValueError as e:
            logger.error(f"LLM 配置无效: {e}")
            return None

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
            "正在启动三方辩论分析 (分析师 → 反方审计师 → 裁判)...\n请稍候，这需要调用多次大模型。"
        )

        case_data = self._build_debate_case(result)
        try:
            engine = DebateEngine(analyst=client, critic=client, judge=client)
            debate = engine.debate(case_data)
            self._render_debate_result(debate)
        except Exception as e:
            logger.error(f"深度辩论失败: {e}")
            self._agent_drawer.add_assistant_message(
                f"辩论分析失败: {e}\n请检查大模型服务是否正常。"
            )

    def _build_debate_case(self, result) -> str:
        """组装辩论案例数据 (校验结果 + 追溯)。"""
        lines = [
            f"规则: {result.rule_id} {result.rule_name}",
            f"公式: {result.formula}",
            f"左侧值: {result.left_value:,.2f} 元",
            f"右侧值: {result.right_value:,.2f} 元",
            f"差额: {result.diff:,.2f} 元 (容差 {result.tolerance})",
            "涉及科目数据来源:",
        ]
        for t in result.trace:
            side = "左侧" if t.side == "left" else "右侧"
            loc = f"第{t.row}行 {t.column}列" if t.row > 0 else "位置未知"
            lines.append(f"  [{side}] {t.name}: {t.amount:,.2f} 元 ({loc})")
        return "\n".join(lines)

    def _render_debate_result(self, debate) -> None:
        """将辩论结果格式化展示在抽屉。"""
        text = (
            "三方辩论分析完成\n\n"
            f"【分析师观点】\n{debate.analyst_view}\n\n"
            f"【反方审计师质疑】\n{debate.critic_view}\n\n"
            f"【裁判最终结论】(置信度: {debate.confidence})\n{debate.final_verdict}"
        )
        self._agent_drawer.add_assistant_message(text)

    def _diagnose_rule(self, rule_id: str) -> None:
        """查找指定规则的失败结果并运行诊断引擎（可选 LLM 增强）。"""
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

        engine = DiagnosisEngine()
        client = self._get_ollama_client()

        # 检查 Ollama 可用性（缓存结果，避免重复探测）
        if self._ollama_available is None:
            try:
                self._ollama_available = client.is_available()
            except Exception:
                self._ollama_available = False

        if self._ollama_available:
            diagnosis = engine.diagnose_with_llm(failed[0], client=client)
            diagnosis += "\n\n（由本地 AI 模型生成）"
        else:
            diagnosis = engine.diagnose(failed[0])
            diagnosis += "\n\n（规则引擎诊断 · 未检测到本地模型）"

        self._agent_drawer.add_assistant_message(diagnosis)

    # ── 窗口事件 ──

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_fab()
        if self._agent_drawer.isVisible():
            self._position_drawer()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape and self._agent_drawer.isVisible():
            self._close_drawer()
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress and obj == self._overlay:
            self._close_drawer()
            return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event) -> None:
        """窗口关闭时释放数据库连接。"""
        self._state.close()
        super().closeEvent(event)

"""主窗口: QMainWindow + 自定义侧边栏 + 顶栏 + AI 抽屉。

替代 FluentWindow, 完全匹配 Demo v4 设计:
- 左侧 240px 自定义侧边栏 (logo + 导航 + 底部版本)
- 顶部 48px 半透明顶栏 (标题 + 副标题 + 操作按钮)
- 中间内容区 (QStackedWidget 切换页面)
- 右下角 AI 浮动按钮
- 右侧 AI 抽屉 (可拖拽缩放 + 遮罩点击收起)

AI 诊断/辩论集成逻辑在 main_window_agent.py (MainWindowAgentMixin) 与
main_window_debate.py (MainWindowDebateMixin); 抽屉/FAB 管理在 main_window_drawer.py。
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import InfoBar, InfoBarPosition

from fsa.gui.app_state import AppState
from fsa.gui.export_helper import export_audit_workbook
from fsa.gui.main_window_agent import MainWindowAgentMixin
from fsa.gui.main_window_debate import MainWindowDebateMixin, _format_trace_loc
from fsa.gui.main_window_drawer import MainWindowDrawerMixin
from fsa.gui.pages.audit_page import AuditPage
from fsa.gui.pages.history_page import HistoryPage
from fsa.gui.pages.import_page import ImportPage
from fsa.gui.pages.rule_page import RulePage
from fsa.gui.pages.settings_page import SettingsPage
from fsa.gui.theme import apply_theme, get_qss, notify_theme_listeners, run_theme_transition
from fsa.gui.widgets.agent_drawer import AgentDrawer
from fsa.gui.widgets.agent_fab import AgentFAB
from fsa.gui.widgets.sidebar import Sidebar
from fsa.gui.widgets.topbar import Topbar

# _format_trace_loc 供外部 (tests/gui/test_agent_worker.py) 从本模块引用
__all__ = ["MainWindow", "_format_trace_loc"]

# 页面 ID 到标题/副标题的映射
_PAGE_TITLES: dict[str, tuple[str, str]] = {
    "navImport": ("数据导入与校验", "准备导入报表"),
    "navAudit": ("审计底稿", "校验结果审计底稿"),
    "navRules": ("规则管理", "勾稽校验规则库"),
    "navHistory": ("历史记录", "校验历史记录"),
    "navSettings": ("系统设置", "系统参数配置"),
}


class MainWindow(QMainWindow, MainWindowDrawerMixin, MainWindowAgentMixin, MainWindowDebateMixin):
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
        # 后台 LLM 任务引用 (防止任务被 GC, 后续可扩展取消)
        self._active_worker = None
        # LLM 可用性缓存 (按 base_url|model 键控, 配置变更自动失效 + 60s TTL)
        self._llm_availability: dict[str, tuple[bool, float]] = {}

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

        def _apply() -> None:
            apply_theme(dark=self._dark)
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if isinstance(app, QApplication):
                app.setStyleSheet(get_qss(self._dark))

        run_theme_transition(self, _apply)
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
        # 显式切回导入页; set_active_nav(emit=False) 仅同步侧边栏高亮,
        # 避免经 nav_changed 信号再次触发 _on_nav 造成双重执行
        self._on_nav("navImport")
        self._sidebar.set_active_nav("navImport", emit=False)
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
        """导出审计底稿 (公共逻辑见 export_helper.py)。"""
        export_audit_workbook(self, self._state.results)

    def _on_results_ready(self) -> None:
        """校验完成后启用导出按钮并显示 FAB 角标。"""
        summary = self._state.results
        self._topbar.set_export_enabled(summary is not None)
        self._update_suggestions()

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
            record = repo.get_by_id(history_id)
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

    def closeEvent(self, event) -> None:
        """窗口关闭时释放数据库连接。"""
        self._state.close()
        super().closeEvent(event)

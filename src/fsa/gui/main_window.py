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
from PySide6.QtCore import QObject, QSettings, Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
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
    "navAudit": ("校验结果", "校验结果一览与导出"),
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

    # 启动更新检查的信号桥 (app.py 注入, 防止被 GC)
    _startup_update_bridge: QObject | None = None

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

        # 延迟创建: 仅首次导航到对应页面时才实例化
        self._rule_page: RulePage | None = None
        self._history_page: HistoryPage | None = None
        self._settings_page: SettingsPage | None = None

        # 记录已创建的页面索引 (避免重复添加)
        self._page_indices: dict[str, int] = {}
        self._stack.addWidget(self._import_page)
        self._page_indices["navImport"] = 0
        self._stack.addWidget(self._audit_page)
        self._page_indices["navAudit"] = 1

        main_layout.addWidget(self._stack, stretch=1)

        root.addWidget(main_area, stretch=1)

        # AI 浮动按钮 (覆盖在主区域上)
        self._agent_fab = AgentFAB(self)
        self._agent_fab.raise_()

        # AI 抽屉 (默认隐藏)
        self._agent_drawer = AgentDrawer(self._state.chat_repo, self)
        self._agent_drawer.hide()
        # 取消信号在抽屉创建后即接线 (此前在首个任务启动时才接线, 提前点击停止无效)
        self.connect_drawer_signals()

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
        self._topbar.validate_clicked.connect(self._import_page.trigger_validate_async)
        self._topbar.export_clicked.connect(self._on_export)

        # 校验完成后启用导出按钮
        self._state.results_changed.connect(self._on_results_ready)

        # AI 按钮
        self._agent_fab.clicked_fab.connect(self._toggle_drawer)
        self._agent_drawer.close_requested.connect(self._close_drawer)
        self._agent_drawer.send_requested.connect(self._on_agent_send)
        self._agent_drawer.typing_changed.connect(self._on_agent_typing)

        # 导入页面状态
        self._import_page.validate_enabled_changed.connect(
            self._topbar.set_validate_enabled
        )
        self._import_page.diagnose_requested.connect(self._on_diagnose)
        self._import_page.debate_requested.connect(self._on_debate)
        self._import_page.history_view_exit_requested.connect(self._on_reset)
        self._audit_page.history_view_exit_requested.connect(self._on_reset)

        # 注意: 历史页面和设置页的信号连接延迟到页面创建时 (见 _ensure_page)

    def _setup_shortcuts(self) -> None:
        ctrl_d = QShortcut(QKeySequence("Ctrl+D"), self)
        ctrl_d.activated.connect(self._toggle_theme)

    # ── 导航 ──

    def _ensure_page(self, nav_id: str) -> int:
        """延迟创建页面 (首次导航时调用), 返回 stack 中的索引。"""
        if nav_id == "navRules" and self._rule_page is None:
            self._rule_page = RulePage(self._state)
            idx = self._stack.count()
            self._stack.addWidget(self._rule_page)
            self._page_indices[nav_id] = idx
        elif nav_id == "navHistory" and self._history_page is None:
            self._history_page = HistoryPage(self._state)
            # 信号连接在页面创建时建立
            self._history_page.view_requested.connect(self._on_view_history)
            idx = self._stack.count()
            self._stack.addWidget(self._history_page)
            self._page_indices[nav_id] = idx
        elif nav_id == "navSettings" and self._settings_page is None:
            self._settings_page = SettingsPage(self._state)
            # 信号连接在页面创建时建立
            self._settings_page.theme_changed.connect(self._on_settings_theme_changed)
            idx = self._stack.count()
            self._stack.addWidget(self._settings_page)
            self._page_indices[nav_id] = idx
        return self._page_indices.get(nav_id, 0)

    def _on_nav(self, nav_id: str) -> None:
        idx = self._ensure_page(nav_id)
        self._stack.setCurrentIndex(idx)
        self._current_nav = nav_id
        # 程序化导航 (如查看历史) 与侧边栏点击共用此入口, 统一高亮状态
        self._sidebar.set_active_nav(nav_id, emit=False)

        title, subtitle = _PAGE_TITLES.get(nav_id, ("", ""))
        self._topbar.set_title(title, subtitle)

        # AI 助手 FAB 仅在"工作区"页面显示 (数据导入 + 审计底稿)
        workspace = nav_id in ("navImport", "navAudit")
        self._agent_fab.setVisible(workspace and not self._agent_drawer.isVisible())
        if not workspace and self._agent_drawer.isVisible():
            self._close_drawer()

        # 历史页面首次展示时触发数据加载
        if nav_id == "navHistory" and self._history_page is not None:
            self._history_page._show_hook()

        # 页面变化后刷新 AI 助手建议问题 (各页面提示不同)
        self._update_suggestions()

    def _get_current_nav(self) -> str:
        """返回当前导航页 ID。"""
        return getattr(self, "_current_nav", "navImport")

    # ── 主题 ──

    def _toggle_theme(self) -> None:
        self._dark = not self._dark
        self._theme_mode = "dark" if self._dark else "light"
        self._apply_theme_change(self._dark)
        # 保存用户显式选择
        settings = QSettings("FSA", "FinancialAudit")
        settings.setValue("theme_mode", self._theme_mode)

    def _apply_theme_change(self, dark: bool) -> None:
        """统一的主题应用入口 (Ctrl+D 与设置页共用, 单入口防重复执行)。"""
        self._dark = dark

        def _apply() -> None:
            apply_theme(dark=dark)
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if isinstance(app, QApplication):
                app.setStyleSheet(get_qss(dark))

        run_theme_transition(self, _apply)
        notify_theme_listeners()
        self._topbar.set_theme_icon(dark)

    def _on_settings_theme_changed(self, dark: bool) -> None:
        """设置页切换主题: 由主窗口统一应用 (settings_page 不直接应用)。"""
        self._theme_mode = "dark" if dark else "light"
        self._apply_theme_change(dark)

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

        try:
            report_types = [ReportType(t) for t in record["report_types"]]
        except (TypeError, ValueError) as e:
            logger.error(f"历史记录 #{history_id} 报表类型无效: {e}")
            InfoBar.error(
                "加载失败", "历史记录中的报表类型无效，无法回看",
                orient=Qt.Orientation.Horizontal, isClosable=True,
                position=InfoBarPosition.TOP, duration=3000, parent=self,
            )
            return

        summary = ValidationSummary(
            period=record["period"] or "",
            total=record["total"],
            passed=record["passed"],
            failed=record["failed"],
            errored=record["errored"],
            skipped=record["skipped"],
            results=results,
            report_types=report_types,
            source_files=record["source_files"],
            source_hashes=record["source_hashes"],
            rule_version=record["rule_version"],
        )
        # 历史结果用轻量表格页展示, 不触发导入页 31+ 张结果卡片的同步重建;
        # 先回填数据, 再切页一次完成, 避免先闪后显
        self._state.set_history_view(summary, history_id)
        self._on_nav("navAudit")
        # 注意: 不再弹 InfoBar —— 页面跳转+结果回填已是充分反馈,
        # 额外提示条会在用户后续点击筛选按钮时造成"弹窗闪现"的干扰
        has_issues = summary.failed + summary.errored > 0
        self._agent_fab.set_badge(has_issues)

    def closeEvent(self, event: QCloseEvent) -> None:
        """窗口关闭时取消后台任务并释放数据库连接。"""
        worker = getattr(self, "_active_worker", None)
        if worker is not None and hasattr(worker, "cancel"):
            worker.cancel()
        self._state.close()
        super().closeEvent(event)

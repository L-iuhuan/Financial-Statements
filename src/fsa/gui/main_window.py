"""主窗口: QMainWindow + 自定义侧边栏 + 顶栏 + AI 抽屉。

替代 FluentWindow, 完全匹配 Demo v4 设计:
- 左侧 240px 自定义侧边栏 (logo + 导航 + 底部版本)
- 顶部 48px 半透明顶栏 (标题 + 副标题 + 操作按钮)
- 中间内容区 (QStackedWidget 切换页面)
- 右下角 AI 浮动按钮
- 右侧 AI 抽屉 (可拖拽缩放 + 遮罩点击收起)
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import Qt, QEvent
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
from fsa.gui.pages.audit_page import AuditPage
from fsa.gui.pages.history_page import HistoryPage
from fsa.gui.pages.import_page import ImportPage
from fsa.gui.pages.rule_page import RulePage
from fsa.gui.pages.settings_page import SettingsPage
from fsa.gui.theme import apply_theme, get_qss
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

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("MainWindow")
        self._state = state
        self._dark = False

        self.setWindowTitle("财务报表勾稽校验系统")
        self.resize(1280, 800)
        self.setMinimumSize(960, 600)

        self._setup_ui()
        self._apply_stylesheet()
        self._connect_signals()
        self._setup_shortcuts()

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

    def _connect_signals(self) -> None:
        # 侧边栏导航
        self._sidebar.nav_changed.connect(self._on_nav)

        # 顶栏按钮
        self._topbar.theme_clicked.connect(self._toggle_theme)
        self._topbar.reset_clicked.connect(self._on_reset)
        self._topbar.validate_clicked.connect(self._import_page.trigger_validate)
        self._topbar.export_clicked.connect(self._on_export)

        # AI 按钮
        self._agent_fab.clicked_fab.connect(self._toggle_drawer)
        self._agent_drawer.close_requested.connect(self._close_drawer)
        self._agent_drawer.send_requested.connect(self._on_agent_send)

        # 导入页面状态
        self._import_page.validate_enabled_changed.connect(
            self._topbar.set_validate_enabled
        )

    def _setup_shortcuts(self) -> None:
        ctrl_d = QShortcut(QKeySequence("Ctrl+D"), self)
        ctrl_d.activated.connect(self._toggle_theme)

    def _apply_stylesheet(self) -> None:
        self.setStyleSheet(get_qss(self._dark))

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

        title, subtitle = _PAGE_TITLES.get(nav_id, ("", ""))
        self._topbar.set_title(title, subtitle)

    # ── 主题 ──

    def _toggle_theme(self) -> None:
        self._dark = not self._dark
        apply_theme(dark=self._dark)
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyleSheet(get_qss(self._dark))
        self._topbar.set_theme_icon(self._dark)

    # ── 重置 ──

    def _on_reset(self) -> None:
        self._state.clear_all()
        self._topbar.set_export_enabled(False)
        self._topbar.set_validate_enabled(False)
        self._sidebar.set_active_nav("navImport")
        self._on_nav("navImport")
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
        InfoBar.info(
            "导出功能",
            "Excel 导出功能正在开发中",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
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

    def _close_drawer(self) -> None:
        self._agent_drawer.hide()
        self._overlay.hide()

    def _position_drawer(self) -> None:
        """定位 AI 抽屉和遮罩层到右侧。"""
        drawer_width = self._agent_drawer.width()
        rect = self.centralWidget().geometry()
        x = rect.right() - drawer_width
        self._agent_drawer.setGeometry(
            x, rect.top(), drawer_width, rect.height()
        )
        self._overlay.setGeometry(rect.left(), rect.top(), rect.width() - drawer_width, rect.height())

    def _on_agent_send(self, text: str) -> None:
        """处理用户发送的消息 (MVP: 简单回复)。"""
        logger.info(f"AI 助手收到消息: {text}")
        # MVP: 简单回复，后续接入 Ollama
        self._agent_drawer.add_assistant_message(
            "已收到您的问题。AI 诊断引擎正在开发中，"
            "届时将接入本地 Ollama 进行智能分析。"
        )

    # ── 窗口事件 ──

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._agent_drawer.isVisible():
            self._position_drawer()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            if self._agent_drawer.isVisible():
                self._close_drawer()
                return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress:
            if obj == self._overlay:
                self._close_drawer()
                return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event) -> None:
        """窗口关闭时释放数据库连接。"""
        self._state.close()
        super().closeEvent(event)

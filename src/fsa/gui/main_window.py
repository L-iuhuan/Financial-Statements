"""主窗口: FluentWindow + 导航 + 主题切换。"""

from __future__ import annotations

from PySide6.QtGui import QKeySequence, QShortcut
from qfluentwidgets import FluentIcon, FluentWindow

from fsa.gui.app_state import AppState
from fsa.gui.pages.import_page import ImportPage
from fsa.gui.pages.rule_page import RulePage
from fsa.gui.pages.settings_page import SettingsPage
from fsa.gui.theme import apply_theme


class MainWindow(FluentWindow):
    """主窗口: 侧边导航 + 多页面。

    快捷键:
        Ctrl+D - 切换深色/亮色主题
    """

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self._state = state
        self._dark = False
        self.setWindowTitle("财务报表勾稽校验系统")
        self.resize(1200, 800)

        self.import_page = ImportPage(state)
        self.rule_page = RulePage(state)
        self.settings_page = SettingsPage(state)

        self.addSubInterface(self.import_page, FluentIcon.FOLDER, "数据导入与校验")
        self.addSubInterface(self.rule_page, FluentIcon.BOOK_SHELF, "规则管理")
        self.addSubInterface(self.settings_page, FluentIcon.SETTING, "系统设置")

        shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        shortcut.activated.connect(self._toggle_theme)

    def _toggle_theme(self) -> None:
        self._dark = not self._dark
        apply_theme(dark=self._dark)

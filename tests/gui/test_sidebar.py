"""侧边栏 (Sidebar) 功能测试: SB-01, SB-02。"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from fsa.core.version import APP_VERSION
from fsa.gui.main_window import MainWindow


class TestSidebarNavigation:
    """测试导航切换 (SB-01)。"""

    def test_click_nav_import_switches_page_and_title(self, qapp, qtbot, app_state) -> None:
        """点击"数据导入"切换页面索引为0并更新顶栏标题 (SB-01)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window._sidebar._nav_buttons["navImport"].clicked_nav.emit("navImport")
        assert window._stack.currentIndex() == 0
        assert window._topbar._title.text() == "数据导入与校验"

    def test_click_nav_audit_switches_page_and_title(self, qapp, qtbot, app_state) -> None:
        """点击"审计底稿"切换页面索引为1并更新顶栏标题 (SB-01)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window._sidebar._nav_buttons["navAudit"].clicked_nav.emit("navAudit")
        assert window._stack.currentIndex() == 1
        assert window._topbar._title.text() == "审计底稿"

    def test_click_nav_rules_switches_page_and_title(self, qapp, qtbot, app_state) -> None:
        """点击"规则管理"切换页面索引为2并更新顶栏标题 (SB-01)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window._sidebar._nav_buttons["navRules"].clicked_nav.emit("navRules")
        assert window._stack.currentIndex() == 2
        assert window._topbar._title.text() == "规则管理"

    def test_click_nav_history_switches_page_and_title(self, qapp, qtbot, app_state) -> None:
        """点击"历史记录"切换页面索引为3并更新顶栏标题 (SB-01)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window._sidebar._nav_buttons["navHistory"].clicked_nav.emit("navHistory")
        assert window._stack.currentIndex() == 3
        assert window._topbar._title.text() == "历史记录"

    def test_click_nav_settings_switches_page_and_title(self, qapp, qtbot, app_state) -> None:
        """点击"系统设置"切换页面索引为4并更新顶栏标题 (SB-01)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window._sidebar._nav_buttons["navSettings"].clicked_nav.emit("navSettings")
        assert window._stack.currentIndex() == 4
        assert window._topbar._title.text() == "系统设置"


class TestSidebarActiveState:
    """测试激活态 (SB-02)。"""

    def test_only_clicked_nav_is_active(self, qapp, qtbot, app_state) -> None:
        """点击某导航项后仅该项 active=True，其余为 False (SB-02)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        window._sidebar._nav_buttons["navAudit"].clicked_nav.emit("navAudit")

        for nav_id, btn in window._sidebar._nav_buttons.items():
            is_active = btn.property("active")
            if nav_id == "navAudit":
                assert is_active is True, f"期望 {nav_id} 激活"
            else:
                assert is_active is False, f"期望 {nav_id} 未激活"

    def test_switching_nav_updates_active_state(self, qapp, qtbot, app_state) -> None:
        """切换导航项后激活态更新 (SB-02)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        # 先点击"规则管理"
        window._sidebar._nav_buttons["navRules"].clicked_nav.emit("navRules")
        assert window._sidebar._nav_buttons["navRules"].property("active") is True

        # 再切换到"历史记录"
        window._sidebar._nav_buttons["navHistory"].clicked_nav.emit("navHistory")
        assert window._sidebar._nav_buttons["navRules"].property("active") is False
        assert window._sidebar._nav_buttons["navHistory"].property("active") is True


class TestSidebarVersion:
    """侧边栏版本号引用 (B-17)。"""

    def test_version_label_uses_app_version(self, qapp, qtbot, app_state) -> None:
        """版本号来自 fsa.core.version.APP_VERSION, 而非硬编码。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        labels = window._sidebar.findChildren(QLabel, "SidebarVersion")
        text = " ".join(lbl.text() for lbl in labels)
        assert APP_VERSION in text

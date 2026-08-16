"""主窗口重置 (_on_reset) 行为测试。

覆盖:
- P0-1: 重置后显式切回导入页 (_current_nav == "navImport", stack 索引为 0)
- P1-6: 重置后 _close_drawer 的 FAB 恢复逻辑正确 (当前页为工作区)
"""

from __future__ import annotations

from fsa.gui.main_window import MainWindow


class TestResetNavigation:
    """P0-1: _on_reset 重置后必须切回导入页。"""

    def test_reset_switches_back_to_import_page(self, qapp, qtbot, app_state) -> None:
        """重置后 _current_nav 与 stack 当前页均为导入页。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        # 先导航到其他页面
        window._on_nav("navAudit")
        assert window._current_nav == "navAudit"
        assert window._stack.currentIndex() == 1

        window._on_reset()

        assert window._current_nav == "navImport"
        assert window._stack.currentIndex() == 0
        # 侧边栏高亮同步到导入项
        assert window._sidebar._nav_buttons["navImport"].property("active") is True

    def test_reset_from_settings_switches_to_import(self, qapp, qtbot, app_state) -> None:
        """从任意非工作区页重置后同样切回导入页。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window._on_nav("navSettings")
        assert window._stack.currentWidget() is window._settings_page

        window._on_reset()

        assert window._current_nav == "navImport"
        assert window._stack.currentIndex() == 0

    def test_reset_clears_state_and_disables_buttons(self, qapp, qtbot, app_state) -> None:
        """重置清空报表/结果并禁用校验与导出按钮。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window._on_nav("navAudit")
        window._on_reset()

        assert window._state.reports == []
        assert window._state.results is None
        assert not window._topbar._validate_btn.isEnabled()
        assert not window._topbar._export_btn.isEnabled()


class TestResetFabRecovery:
    """P1-6: 重置后 _close_drawer 的 FAB 恢复逻辑。"""

    def test_close_drawer_after_reset_restores_fab(self, qapp, qtbot, app_state) -> None:
        """重置切回导入页 (工作区) 后, 关闭抽屉恢复 FAB。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window._on_nav("navSettings")
        window._open_drawer()
        assert window._agent_fab.isHidden()  # 抽屉打开时 FAB 隐藏

        window._on_reset()  # 重置回导入页
        window._close_drawer()
        assert not window._agent_fab.isHidden()  # 当前页为工作区 -> FAB 恢复

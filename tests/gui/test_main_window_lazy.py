"""主窗口懒加载页面测试 (FIX 1)。

覆盖:
- 启动时不创建 rule_page / history_page / settings_page
- 导航到页面时创建一次
- 二次导航复用同一实例
- 延迟页面的信号连接在创建时建立
- history_page 首次展示时才加载历史数据
"""

from __future__ import annotations

from unittest.mock import patch

from fsa.gui.main_window import MainWindow
from fsa.gui.pages.history_page import HistoryPage
from fsa.gui.pages.rule_page import RulePage
from fsa.gui.pages.settings_page import SettingsPage


class TestLazyPageCreation:
    """启动时仅创建导入页和审计页，其他页面延迟创建。"""

    def test_startup_does_not_create_deferred_pages(self, qapp, qtbot, app_state) -> None:
        """窗口启动时 rule_page / history_page / settings_page 为 None。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        assert window._rule_page is None, "rule_page 应在启动时为 None"
        assert window._history_page is None, "history_page 应在启动时为 None"
        assert window._settings_page is None, "settings_page 应在启动时为 None"

    def test_startup_eager_pages_exist(self, qapp, qtbot, app_state) -> None:
        """窗口启动时 import_page 和 audit_page 已创建。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        assert window._import_page is not None, "import_page 应在启动时创建"
        assert window._audit_page is not None, "audit_page 应在启动时创建"

    def test_navigate_creates_rule_page_once(self, qapp, qtbot, app_state) -> None:
        """导航到规则页时才创建，第二次导航复用同一实例。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        window._on_nav("navRules")
        assert window._rule_page is not None, "导航后 rule_page 应已创建"
        assert isinstance(window._rule_page, RulePage)
        first = window._rule_page

        # 切走再切回
        window._on_nav("navImport")
        window._on_nav("navRules")
        assert window._rule_page is first, "第二次导航应复用同一实例"

    def test_navigate_creates_history_page_once(self, qapp, qtbot, app_state) -> None:
        """导航到历史页时才创建，第二次导航复用同一实例。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        window._on_nav("navHistory")
        assert window._history_page is not None
        assert isinstance(window._history_page, HistoryPage)
        first = window._history_page

        window._on_nav("navImport")
        window._on_nav("navHistory")
        assert window._history_page is first

    def test_navigate_creates_settings_page_once(self, qapp, qtbot, app_state) -> None:
        """导航到设置页时才创建，第二次导航复用同一实例。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        window._on_nav("navSettings")
        assert window._settings_page is not None
        assert isinstance(window._settings_page, SettingsPage)
        first = window._settings_page

        window._on_nav("navImport")
        window._on_nav("navSettings")
        assert window._settings_page is first


class TestHistoryPageDeferredLoad:
    """history_page 首次展示时才加载历史数据 (不预先查 SQLite)。"""

    def test_history_page_does_not_load_on_construction(self, qapp, qtbot, app_state) -> None:
        """构造 HistoryPage 时不自动调用 _load_history (由首次展示触发)。"""
        with patch.object(HistoryPage, "_load_history") as mock_load:
            HistoryPage(app_state)
            # 构造时不应调用 _load_history
            mock_load.assert_not_called()

    def test_history_page_loads_on_first_navigation(self, qapp, qtbot, app_state) -> None:
        """首次导航到历史页时加载数据。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        with patch.object(HistoryPage, "_load_history") as mock_load:
            window._on_nav("navHistory")
            # 首次导航应触发加载
            mock_load.assert_called_once()

    def test_history_page_second_navigation_reuses_no_reload(self, qapp, qtbot, app_state) -> None:
        """第二次导航到历史页时不再调用 _load_history (由 _connect_signals 的 history_changed 驱动)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        window._on_nav("navHistory")
        window._on_nav("navImport")

        with patch.object(HistoryPage, "_load_history") as mock_load:
            window._on_nav("navHistory")
            # 第二次导航不应再次触发 _load_history
            mock_load.assert_not_called()


class TestSignalConnectionsWhenDeferred:
    """延迟创建的页面信号连接在创建时正确建立。"""

    def test_history_page_view_requested_connected(self, qapp, qtbot, app_state) -> None:
        """history_page.view_requested 信号在延迟创建时连接到 _on_view_history。
        验证: 发射信号后 _on_nav 被调用切回导入页。
        """
        from unittest.mock import MagicMock

        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        window._on_nav("navHistory")
        assert window._history_page is not None

        # 验证信号连接: 发射 view_requested 应触发 _on_view_history 逻辑
        # (通过 mock _on_view_history 来验证)
        window._on_view_history = MagicMock()  # type: ignore[method-assign]
        window._history_page.view_requested.emit(1)
        window._on_view_history.assert_called_once_with(1)

    def test_settings_page_theme_changed_connected(self, qapp, qtbot, app_state) -> None:
        """settings_page.theme_changed 信号在延迟创建时连接到 _on_settings_theme_changed。
        验证: 发射信号后主窗口 _dark 状态同步。
        """
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        window._on_nav("navSettings")
        assert window._settings_page is not None

        # 发射 theme_changed(True) -> _on_settings_theme_changed 应设置 _dark=True
        window._settings_page.theme_changed.emit(True)
        assert window._dark is True


class TestFabAndTitleWithDeferredPages:
    """FAB 可见性和页面标题映射正确处理未创建的页面。"""

    def test_fab_hidden_when_navigating_to_deferred_pages(self, qapp, qtbot, app_state) -> None:
        """导航到非工作区页面时 FAB 隐藏 (即使页面尚未创建)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        # 先打开 FAB
        window._agent_fab.show()
        assert not window._agent_fab.isHidden()

        # 导航到规则页 (非工作区)
        window._on_nav("navRules")
        assert window._agent_fab.isHidden()

    def test_page_title_for_deferred_pages(self, qapp, qtbot, app_state) -> None:
        """未创建的页面也有正确的标题映射。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        window._on_nav("navRules")
        # 检查顶栏标题已设置 (通过 _PAGE_TITLES 映射)
        assert window._topbar._title.text() == "规则管理"

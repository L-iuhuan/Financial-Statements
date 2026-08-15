"""主题切换收敛测试 (FIX 3)。

覆盖:
- agent_drawer._on_theme_changed 不再遍历所有子控件
- settings_page._set_theme 不再直接调用 apply_theme/setStyleSheet
- Ctrl+D 和 settings 路径各自仅应用一次主题
"""

from __future__ import annotations

from unittest.mock import patch

from PySide6.QtWidgets import QWidget

from fsa.gui.main_window import MainWindow
from fsa.gui.pages.settings_page import SettingsPage
from fsa.gui.widgets.agent_drawer import AgentDrawer


class TestAgentDrawerThemeScope:
    """agent_drawer._on_theme_changed 仅 repolish 特定控件，而非全树遍历。"""

    def test_on_theme_changed_does_not_walk_children(self, qapp, qtbot) -> None:
        """_on_theme_changed 不再对每个子控件执行 unpolish/polish 全树遍历。"""
        drawer = AgentDrawer(chat_repo=None)
        qtbot.addWidget(drawer)

        # 添加一些子控件
        from PySide6.QtWidgets import QLabel, QPushButton

        inner = QWidget(drawer)
        inner.setObjectName("TestInner")
        child_label = QLabel("test", inner)
        child_label.setObjectName("TestChildLabel")
        child_btn = QPushButton("btn", inner)
        child_btn.setObjectName("TestChildBtn")

        # 对 drawer.style() 的 polish/unpolish 调用应限于 drawer 自身和特定子控件
        # 不再对 inner 及其子控件执行
        with (
            patch.object(drawer.style(), "unpolish", wraps=drawer.style().unpolish),
            patch.object(drawer.style(), "polish", wraps=drawer.style().polish) as mock_polish,
        ):
            drawer._on_theme_changed()

        # 检查: drawer 自身仍被 repolish
        drawer_polished = any(
            call_args[0][0] is drawer for call_args in mock_polish.call_args_list
        )
        assert drawer_polished, "drawer 自身仍应被 repolish"

        # 检查: inner 和其子控件不应被 repolish
        inner_polished = any(
            call_args[0][0] is inner for call_args in mock_polish.call_args_list
        )
        child_label_polished = any(
            call_args[0][0] is child_label for call_args in mock_polish.call_args_list
        )
        child_btn_polished = any(
            call_args[0][0] is child_btn for call_args in mock_polish.call_args_list
        )
        assert not inner_polished, "inner 不应被 repolish"
        assert not child_label_polished, "child_label 不应被 repolish"
        assert not child_btn_polished, "child_btn 不应被 repolish"

    def test_on_theme_changed_repolishes_shell_widgets(self, qapp, qtbot) -> None:
        """_on_theme_changed 仍 repolish 抽屉壳层关键控件 (header/context_bar/input)。"""
        drawer = AgentDrawer(chat_repo=None)
        qtbot.addWidget(drawer)

        with patch.object(
            drawer.style(), "unpolish", wraps=drawer.style().unpolish
        ) as mock_unpolish:
            drawer._on_theme_changed()

        polished_widgets = {call_args[0][0] for call_args in mock_unpolish.call_args_list}
        # 抽屉自身
        assert drawer in polished_widgets, "drawer 自身应被 repolish"
        # 壳层控件
        assert drawer._header in polished_widgets, "header 应被 repolish"
        assert drawer._context_bar in polished_widgets, "context_bar 应被 repolish"
        assert drawer._input in polished_widgets, "input 应被 repolish"


class TestSettingsThemeConvergence:
    """settings_page._set_theme 不再直接 apply_theme/setStyleSheet，统一由 main_window 应用。"""

    def test_settings_theme_does_not_apply_directly(self, qapp, qtbot, app_state) -> None:
        """settings_page._set_theme 不再调用 apply_theme/get_qss。"""
        page = SettingsPage(app_state)
        qtbot.addWidget(page)

        with (
            patch("fsa.gui.pages.settings_page.apply_theme", create=True) as mock_apply,
            patch("fsa.gui.pages.settings_page.get_qss", return_value="", create=True) as mock_qss,
        ):
                page._set_theme("dark")

        mock_apply.assert_not_called()
        mock_qss.assert_not_called()

    def test_settings_theme_emits_signal(self, qapp, qtbot, app_state) -> None:
        """settings_page._set_theme 仅发射 theme_changed 信号。"""
        page = SettingsPage(app_state)
        qtbot.addWidget(page)

        received: list[bool] = []
        page.theme_changed.connect(lambda dark: received.append(dark))

        page._set_theme("dark")
        assert received == [True]

    def test_main_window_on_settings_theme_changed_applies_theme(self, qapp, qtbot, app_state) -> None:
        """main_window._on_settings_theme_changed 负责应用主题。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        with (
            patch("fsa.gui.main_window.apply_theme") as mock_apply,
            patch("fsa.gui.main_window.get_qss", return_value="") as mock_qss,
        ):
                window._on_settings_theme_changed(True)

        mock_apply.assert_called_once_with(dark=True)
        # get_qss 在 run_theme_transition 的回调中调用，验证至少被调用
        assert mock_qss.call_count >= 1

    def test_ctrl_d_applies_theme_once(self, qapp, qtbot, app_state) -> None:
        """Ctrl+D 路径仅应用一次主题 (不重复)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        with (
            patch("fsa.gui.main_window.apply_theme") as mock_apply,
            patch("fsa.gui.main_window.get_qss", return_value="") as mock_qss,
        ):
                window._toggle_theme()

        assert mock_apply.call_count == 1
        assert mock_qss.call_count == 1

    def test_settings_path_applies_theme_once(self, qapp, qtbot, app_state) -> None:
        """settings 路径仅应用一次主题 (settings_page 不直接 apply, main_window 只 apply 一次)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        window._on_nav("navSettings")
        assert window._settings_page is not None

        with (
            patch("fsa.gui.main_window.apply_theme") as mock_apply,
            patch("fsa.gui.main_window.get_qss", return_value="") as mock_qss,
        ):
                window._settings_page.theme_changed.emit(True)

        assert mock_apply.call_count == 1
        assert mock_qss.call_count == 1


class TestSettingsPageSetThemeNoRunTransition:
    """settings_page._set_theme 不再调用 run_theme_transition。"""

    def test_set_theme_does_not_call_run_transition(self, qapp, qtbot, app_state) -> None:
        """_set_theme 不调用 run_theme_transition (由 main_window 负责)。"""
        page = SettingsPage(app_state)
        qtbot.addWidget(page)

        with patch("fsa.gui.pages.settings_page.run_theme_transition", create=True) as mock_trans:
            page._set_theme("dark")

        mock_trans.assert_not_called()

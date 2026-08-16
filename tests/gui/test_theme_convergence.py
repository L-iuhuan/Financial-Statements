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
from fsa.gui.theme import apply_theme, get_qss
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


class TestThemeQssTokens:
    """QSS 令牌存在性: 关键控件在双主题下均有完整样式规则。"""

    def test_qss_contains_qcombobox_rules(self, qapp) -> None:
        """QSS 包含 QComboBox / 下拉列表 / 下拉箭头规则。"""
        for dark in (False, True):
            qss = get_qss(dark)
            assert "QComboBox {" in qss
            assert "QComboBox::down-arrow" in qss
            assert "QComboBox QAbstractItemView" in qss
            assert "QComboBox QAbstractItemView::item:selected" in qss

    def test_qss_contains_period_picker_rules(self, qapp) -> None:
        """QSS 包含 PeriodPicker (文本框+箭头按钮) 与 DropdownButton 规则。"""
        for dark in (False, True):
            qss = get_qss(dark)
            assert "QLineEdit#PeriodInput" in qss
            assert "QPushButton#PeriodArrowBtn" in qss
            assert "QPushButton#DropdownButton" in qss

    def test_qss_contains_agent_bubble_rules(self, qapp) -> None:
        """QSS 包含 AI 助手气泡与关于区版本摘要规则。"""
        for dark in (False, True):
            qss = get_qss(dark)
            assert "QLabel#AgentBubbleUser" in qss
            assert "QTextBrowser#AgentBubbleAssistant" in qss
            assert "QLabel#AboutVersionSummary" in qss

    def test_qss_textbtn_has_padding(self, qapp) -> None:
        """TextBtn 含内边距 (修复「填入模板」等按钮仅 18px 高的挤压问题)。"""
        for dark in (False, True):
            qss = get_qss(dark)
            assert "QPushButton#TextBtn" in qss
            assert "padding: 6px 12px" in qss


class TestDropdownArrowRendering:
    """下拉箭头真实渲染回归 (像素级): PeriodPicker/DropdownCombo 自绘箭头。

    修复背景: QDateEdit/QComboBox 的子控件 QSS (::drop-down/::down-arrow)
    在部分 Windows 环境不渲染, 反复纯 QSS 修复无效; 改为复合控件 + QPainter
    自绘箭头, 本类验证箭头颜色像素确实绘制。
    """

    @staticmethod
    def _arrow_pixels(qapp, widget, color: tuple[int, int, int]) -> int:
        from PySide6.QtGui import QImage

        app = qapp
        app.processEvents()
        img = widget.grab().toImage().convertToFormat(QImage.Format.Format_RGB32)
        n = 0
        for y in range(img.height()):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                if (
                    abs(c.red() - color[0]) <= 25
                    and abs(c.green() - color[1]) <= 25
                    and abs(c.blue() - color[2]) <= 25
                ):
                    n += 1
        return n

    def test_period_picker_arrow_renders_in_both_themes(self, qapp, qtbot) -> None:
        """PeriodPicker 自绘箭头在明暗主题下均有像素渲染。"""
        from PySide6.QtCore import QDate
        from PySide6.QtWidgets import QVBoxLayout, QWidget

        from fsa.gui.widgets.period_picker import PeriodPicker

        old_qss = qapp.styleSheet()
        try:
            for dark, color in ((False, (0x6B, 0x72, 0x80)), (True, (0x9C, 0xA3, 0xAF))):
                # 与生产一致: apply_theme 切换令牌 (自绘箭头读 current_palette) + QSS
                apply_theme(dark=dark)
                qapp.setStyleSheet(get_qss(dark))
                picker = PeriodPicker(QDate(2026, 8, 16))
                picker.setFixedWidth(130)
                host = QWidget()
                lay = QVBoxLayout(host)
                lay.addWidget(picker)
                qtbot.addWidget(host)
                host.show()
                qapp.processEvents()
                assert self._arrow_pixels(qapp, picker._btn, color) > 10, (
                    f"dark={dark}: 日期选择器箭头未渲染"
                )
                host.close()
        finally:
            apply_theme(dark=False)
            qapp.setStyleSheet(old_qss)

    def test_period_picker_click_opens_calendar_popup(self, qapp, qtbot) -> None:
        """点击 PeriodPicker 箭头按钮打开日历弹窗。"""
        from PySide6.QtCore import QDate
        from PySide6.QtWidgets import QVBoxLayout, QWidget

        from fsa.gui.widgets.period_picker import PeriodPicker

        old_qss = qapp.styleSheet()
        try:
            qapp.setStyleSheet(get_qss(False))
            picker = PeriodPicker(QDate(2026, 8, 16))
            picker.setFixedWidth(130)
            host = QWidget()
            lay = QVBoxLayout(host)
            lay.addWidget(picker)
            qtbot.addWidget(host)
            host.show()
            qapp.processEvents()
            # 用定时器在弹窗 exec 期间点选日历并关闭
            from PySide6.QtCore import QTimer

            def _pick() -> None:
                from PySide6.QtWidgets import QCalendarWidget

                cals = [w for w in qapp.allWidgets() if isinstance(w, QCalendarWidget) and w.isVisible()]
                assert cals, "日历弹窗未打开"
                cals[0].clicked.emit(QDate(2026, 7, 1))
                cals[0].window().close()

            QTimer.singleShot(150, _pick)
            picker._show_calendar()
            qapp.processEvents()
            assert picker.date() == QDate(2026, 7, 1), "选中的日期应回填"
            host.close()
        finally:
            qapp.setStyleSheet(old_qss)

    def test_dropdown_combo_arrow_renders_in_both_themes(self, qapp, qtbot) -> None:
        """DropdownCombo 自绘箭头在明暗主题下均有像素渲染。"""
        from PySide6.QtWidgets import QVBoxLayout, QWidget

        from fsa.gui.widgets.dropdown_combo import DropdownCombo

        old_qss = qapp.styleSheet()
        try:
            for dark, color in ((False, (0x6B, 0x72, 0x80)), (True, (0x9C, 0xA3, 0xAF))):
                # 与生产一致: apply_theme 切换令牌 (自绘箭头读 current_palette) + QSS
                apply_theme(dark=dark)
                qapp.setStyleSheet(get_qss(dark))
                combo = DropdownCombo()
                combo.addItem("通用（默认）", "general")
                combo.addItem("金融", "financial")
                combo.setFixedWidth(140)
                host = QWidget()
                lay = QVBoxLayout(host)
                lay.addWidget(combo)
                qtbot.addWidget(host)
                host.show()
                qapp.processEvents()
                assert self._arrow_pixels(qapp, combo._button, color) > 10, (
                    f"dark={dark}: 下拉按钮箭头未渲染"
                )
                host.close()
        finally:
            apply_theme(dark=False)
            qapp.setStyleSheet(old_qss)


class TestThemePalette:
    """主题调色板: apply_theme 同步设置明暗 QPalette, 兜底无 QSS 规则的原生控件。"""

    def test_apply_theme_sets_dark_palette(self, qapp) -> None:
        from PySide6.QtGui import QPalette

        try:
            apply_theme(dark=True)
            window = qapp.palette().color(QPalette.ColorRole.Window)
            button = qapp.palette().color(QPalette.ColorRole.Button)
            assert window.lightness() < 80, f"暗色 Window 亮度 {window.lightness()}"
            assert button.lightness() < 80, f"暗色 Button 亮度 {button.lightness()}"
        finally:
            apply_theme(dark=False)

    def test_apply_theme_restores_light_palette(self, qapp) -> None:
        from PySide6.QtGui import QPalette

        apply_theme(dark=True)
        try:
            apply_theme(dark=False)
            window = qapp.palette().color(QPalette.ColorRole.Window)
            assert window.lightness() > 200, f"浅色 Window 亮度 {window.lightness()}"
        finally:
            apply_theme(dark=False)


class TestSettingsUpdateButtonsStyled:
    """设置页更新按钮: 检查更新/下载更新须有 QSS objectName (深色主题一致)。"""

    def test_update_buttons_have_styled_object_names(self, qapp, qtbot, app_state) -> None:
        page = SettingsPage(app_state)
        qtbot.addWidget(page)
        assert page._update_check_btn.objectName() == "BtnSecondary"
        assert page._update_download_btn.objectName() == "BtnPrimary"

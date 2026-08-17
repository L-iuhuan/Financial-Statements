"""顶栏 (Topbar) 功能测试: TB-01..TB-05。"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest

from fsa.gui.main_window import MainWindow

_TEST_ROOT = Path(__file__).resolve().parent
_PROJECT_ROOT = _TEST_ROOT.parent.parent
_MOUTAI_FILE = _PROJECT_ROOT / "tests" / "fixtures" / "real_reports" / "贵州茅台_2023年报_三大报表.xlsx"
pytestmark = pytest.mark.skipif(
    not _MOUTAI_FILE.exists(),
    reason="真实年报 fixture 缺失（合规红线：已移出 git，需手动放置）",
)



class TestTopbarThemeToggle:
    """测试主题切换按钮 (TB-01, TB-02)。"""

    def test_theme_toggle_button_flips_dark_state(self, qapp, qtbot, app_state) -> None:
        """点击主题按钮后 _dark 翻转 (TB-01)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        assert window._dark is False

        window._topbar.theme_clicked.emit()
        assert window._dark is True

        window._topbar.theme_clicked.emit()
        assert window._dark is False

    def test_theme_button_icon_changes_on_toggle(self, qapp, qtbot, app_state) -> None:
        """切换主题后图标变化 (TB-01)。图标为 FluentIcon, 非空。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        assert not window._topbar._theme_btn.icon().isNull()

        window._topbar.theme_clicked.emit()
        assert not window._topbar._theme_btn.icon().isNull()

    def test_ctrl_d_shortcut_toggles_theme(self, qapp, qtbot, app_state) -> None:
        """Ctrl+D 快捷键触发主题切换 (TB-02)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.show()
        qtbot.wait(50)
        assert window._dark is False

        QTest.keySequence(window, QKeySequence("Ctrl+D"))
        qtbot.wait(50)
        assert window._dark is True


class TestTopbarReset:
    """测试重置按钮 (TB-03)。"""

    def test_reset_clears_reports_and_disables_buttons(self, qapp, qtbot, app_state) -> None:
        """重置后报表清空、校验/导出按钮禁用、跳回导入页 (TB-03)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        app_state.load_registry()

        # 先导入报表并校验，使按钮启用
        window._import_page._on_file(str(_MOUTAI_FILE))
        assert len(app_state.reports) > 0
        assert window._topbar._validate_btn.isEnabled() is True

        # 执行校验
        window._topbar.validate_clicked.emit()
        qtbot.wait(100)
        assert app_state.results is not None

        # 执行重置
        window._topbar.reset_clicked.emit()

        # 报表清空
        assert len(app_state.reports) == 0
        # 结果清空
        assert app_state.results is None
        # 校验按钮禁用
        assert window._topbar._validate_btn.isEnabled() is False
        # 导出按钮禁用
        assert window._topbar._export_btn.isEnabled() is False
        # 跳回导入页
        assert window._stack.currentIndex() == 0


class TestTopbarValidateButton:
    """测试执行校验按钮 (TB-04)。"""

    def test_validate_disabled_without_reports(self, qapp, qtbot, app_state) -> None:
        """无报表时校验按钮禁用 (TB-04)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        assert window._topbar._validate_btn.isEnabled() is False

    def test_validate_enabled_after_import(self, qapp, qtbot, app_state) -> None:
        """导入报表后校验按钮启用 (TB-04)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window._import_page._on_file(str(_MOUTAI_FILE))
        assert window._topbar._validate_btn.isEnabled() is True


class TestTopbarExportButton:
    """测试导出底稿按钮 (TB-05)。"""

    def test_export_disabled_without_results(self, qapp, qtbot, app_state) -> None:
        """无结果时导出按钮禁用 (TB-05)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        assert window._topbar._export_btn.isEnabled() is False

    def test_export_enabled_after_validation(self, qapp, qtbot, app_state) -> None:
        """校验完成后导出按钮启用 (TB-05)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        app_state.load_registry()

        window._import_page._on_file(str(_MOUTAI_FILE))
        window._topbar.validate_clicked.emit()
        qtbot.wait(100)
        assert window._topbar._export_btn.isEnabled() is True


class TestTopbarUpdateBadge:
    """测试顶栏更新角标 (TB-06): 默认隐藏 / 显示带版本 tooltip / 隐藏 / 点击发信号。"""

    def test_update_badge_hidden_by_default(self, qapp, qtbot, app_state) -> None:
        """未发现新版本时角标按钮默认隐藏 (TB-06)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        assert window._topbar._update_badge_btn.isHidden()

    def test_show_update_badge_shows_with_version_tooltip(self, qapp, qtbot, app_state) -> None:
        """show_update_badge 显示按钮并带版本 tooltip (TB-06)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.show()
        window._topbar.show_update_badge("0.5.0")
        assert window._topbar._update_badge_btn.isVisible()
        assert "0.5.0" in window._topbar._update_badge_btn.toolTip()

    def test_hide_update_badge_hides(self, qapp, qtbot, app_state) -> None:
        """hide_update_badge 隐藏角标 (TB-06)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.show()
        window._topbar.show_update_badge("0.5.0")
        assert window._topbar._update_badge_btn.isVisible()
        window._topbar.hide_update_badge()
        assert window._topbar._update_badge_btn.isHidden()

    def test_update_badge_click_emits_signal(self, qapp, qtbot, app_state) -> None:
        """点击角标发出 update_badge_clicked 信号 (TB-06)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.show()
        fired: list[bool] = []
        window._topbar.update_badge_clicked.connect(lambda: fired.append(True))
        window._topbar._update_badge_btn.show()
        window._topbar._update_badge_btn.click()
        assert fired == [True]

"""布局测试 (Layout): LT-01, LT-04。"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QPushButton, QScrollArea

from fsa.gui.main_window import MainWindow

_TEST_ROOT = Path(__file__).resolve().parent
_PROJECT_ROOT = _TEST_ROOT.parent.parent
_MOUTAI_FILE = _PROJECT_ROOT / "tests" / "fixtures" / "real_reports" / "贵州茅台_2023年报_三大报表.xlsx"
pytestmark = pytest.mark.skipif(
    not _MOUTAI_FILE.exists(),
    reason="真实年报 fixture 缺失（合规红线：已移出 git，需手动放置）",
)



class TestLayoutNoHorizontalScroll:
    """测试最小窗口无水平滚动条 (LT-01)。"""

    def test_no_horizontal_scrollbar_on_all_pages(self, qapp, qtbot, app_state) -> None:
        """在 960×600 最小窗口下所有页面无可见水平滚动条 (LT-01)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.resize(960, 600)
        app_state.load_registry()

        # 导入报表以获得非空页面状态
        window._import_page._on_file(str(_MOUTAI_FILE))
        qtbot.wait(100)
        window._topbar.validate_clicked.emit()
        qtbot.wait(100)

        # 遍历所有 5 个页面
        nav_ids = ["navImport", "navAudit", "navRules", "navHistory", "navSettings"]
        for nav_id in nav_ids:
            window._sidebar._nav_buttons[nav_id].clicked_nav.emit(nav_id)
            qtbot.wait(50)

            # 查找所有 QScrollArea
            scroll_areas = window.findChildren(QScrollArea)
            for sa in scroll_areas:
                if sa.isVisible():
                    hbar = sa.horizontalScrollBar()
                    if hbar is not None:
                        assert not hbar.isVisible(), (
                            f"页面 {nav_id} 的 QScrollArea 有可见水平滚动条"
                        )


class TestButtonTextTruncation:
    """测试按钮文字无截断 (LT-04)。"""

    def test_no_button_text_truncated(self, qapp, qtbot, app_state) -> None:
        """所有 QPushButton 文字不被截断 (LT-04)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.resize(1280, 800)
        app_state.load_registry()

        # 导入报表以获得完整 UI
        window._import_page._on_file(str(_MOUTAI_FILE))
        qtbot.wait(100)
        window._topbar.validate_clicked.emit()
        qtbot.wait(100)

        # 遍历所有页面确保按钮都显示
        nav_ids = ["navImport", "navAudit", "navRules", "navHistory", "navSettings"]
        for nav_id in nav_ids:
            window._sidebar._nav_buttons[nav_id].clicked_nav.emit(nav_id)
            qtbot.wait(50)

        # 检查所有可见按钮
        buttons = window.findChildren(QPushButton)
        tolerance = 4  # 小像素容差
        for btn in buttons:
            if not btn.isVisible():
                continue
            text = btn.text()
            if not text:
                continue
            hint = btn.sizeHint()
            actual = btn.size()
            assert hint.width() <= actual.width() + tolerance, (
                f"按钮文字可能截断: '{text}' "
                f"(sizeHint={hint.width()} > actual={actual.width()})"
            )

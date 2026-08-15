"""针对 2026-08 审查修复的回归测试。

覆盖:
- FAB 消息图标必须为白色 (不再使用 colored().icon() 的错误 API)
- 表格 QSS 去除 focus outline, 避免 Windows 下点击单元格出现黑色方框
- 查看历史后: 页面/侧边栏/状态/横幅/滚动位置一致
- 抽屉最小宽度下消息气泡不超出消息区视口
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QTableWidget

from fsa.core.models.result import ValidationSummary
from fsa.core.models.rule import Severity
from fsa.gui.main_window import MainWindow
from fsa.gui.theme import get_qss
from fsa.gui.widgets.agent_fab import AgentFAB
from tests.gui.helpers import make_result


def _icon_dominant_color(icon) -> tuple[int, int, int] | None:
    """统计图标非透明像素中最多的颜色。"""
    image = icon.pixmap(22, 22).toImage()
    counts: dict[tuple[int, int, int], int] = {}
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.alpha() < 32:
                continue
            key = (color.red(), color.green(), color.blue())
            counts[key] = counts.get(key, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


class TestFabIconWhite:
    def test_fab_message_icon_is_white(self, qapp, qtbot) -> None:
        """FAB 图标主色应为白色, 不能是默认黑色。"""
        fab = AgentFAB()
        qtbot.addWidget(fab)

        color = _icon_dominant_color(fab.icon())
        assert color is not None
        assert color == (255, 255, 255), f"FAB 图标主色应为白色, 实际 {color}"


class TestTableFocusOutline:
    def test_table_qss_disables_focus_outline(self) -> None:
        """表格 QSS 必须显式关闭 outline, 消除点击单元格的黑色焦点框。"""
        for dark in (False, True):
            qss = get_qss(dark)
            assert "QTableWidget {" in qss
            assert "outline: none;" in qss

    def test_table_widget_still_usable(self, qapp, qtbot) -> None:
        """表格仍可正常选中单元格。"""
        table = QTableWidget(1, 1)
        qtbot.addWidget(table)
        table.show()
        QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
        assert table.currentColumn() >= 0


class TestHistoryViewNavigation:
    def test_view_history_syncs_state_sidebar_and_scroll(
        self, qapp, qtbot, app_state
    ) -> None:
        """查看历史后进入导入页, 侧边栏/历史状态/横幅/滚动位置一致。"""
        results = [
            make_result("A-001", passed=True, severity=Severity.ERROR),
            make_result("B-001", passed=False, severity=Severity.ERROR, diff=1.0),
        ]
        summary = ValidationSummary(
            period="2024-12",
            total=len(results),
            passed=1,
            failed=1,
            results=results,
        )
        history_id = app_state.history_repo.save(summary)  # type: ignore[union-attr]

        # 先制造一个实时报表与结果, 验证历史回看会清空实时数据
        app_state.set_reports([])
        app_state.set_results(summary, persist=False)

        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.show()
        qtbot.wait(20)

        window._import_page._scroll.verticalScrollBar().setValue(999)
        window._sidebar._nav_buttons["navHistory"].clicked_nav.emit("navHistory")
        qtbot.wait(20)

        window._on_view_history(history_id)
        qtbot.wait(20)

        assert window._stack.currentIndex() == 0
        assert window._get_current_nav() == "navImport"
        assert window._sidebar._nav_buttons["navImport"].property("active") is True
        assert window._sidebar._nav_buttons["navHistory"].property("active") is False
        assert app_state.history_view_id == history_id
        assert app_state.reports == []
        assert window._import_page._history_banner.isVisible()
        assert f"历史回看 #{history_id}" in window._import_page._history_banner_text.text()
        assert window._import_page._scroll.verticalScrollBar().value() == 0

    def test_importing_new_file_exits_history_view(
        self, qapp, qtbot, app_state
    ) -> None:
        """进入历史回看后重新导入文件, 自动退出回看并隐藏横幅。"""
        results = [make_result("A-001", passed=True)]
        summary = ValidationSummary(total=1, passed=1, results=results)
        app_state.set_history_view(summary, 42)
        assert app_state.history_view_id == 42

        app_state.set_reports([])
        assert app_state.history_view_id is None


class TestDrawerBubbleFitsViewport:
    def test_bubbles_do_not_overflow_min_drawer(self, qapp, qtbot, app_state) -> None:
        """抽屉缩到最小宽度时, 消息气泡右缘不超过消息区视口。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        window.resize(1280, 800)
        window.show()
        window._open_drawer()
        drawer = window._agent_drawer
        qtbot.wait(20)

        drawer.add_user_message("用户消息" * 80)
        drawer.add_assistant_message("AI 回答" * 120)
        qtbot.wait(20)

        drawer.resize(drawer.MIN_WIDTH, drawer.height())
        qtbot.wait(30)

        viewport_width = drawer._scroll.viewport().width()
        for bubble in [*drawer._user_bubbles, *drawer._ai_bubbles]:
            left = bubble.mapTo(drawer._scroll.viewport(), QPoint(0, 0)).x()
            assert left >= 0
            assert left + bubble.width() <= viewport_width + 1, (
                f"气泡右缘 {left + bubble.width()} 超出视口 {viewport_width}"
            )

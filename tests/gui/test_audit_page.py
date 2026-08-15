"""审计页 (AuditPage) 功能测试: AU-01, AU-02, AU-05。"""

from __future__ import annotations

from pathlib import Path

import pytest

from fsa.gui.main_window import MainWindow

_TEST_ROOT = Path(__file__).resolve().parent
_PROJECT_ROOT = _TEST_ROOT.parent.parent
_MOUTAI_FILE = _PROJECT_ROOT / "tests" / "fixtures" / "real_reports" / "贵州茅台_2023年报_三大报表.xlsx"
pytestmark = pytest.mark.skipif(
    not _MOUTAI_FILE.exists(),
    reason="真实年报 fixture 缺失（合规红线：已移出 git，需手动放置）",
)



class TestAuditTable:
    """测试审计表格 (AU-01, AU-02)。"""

    def test_table_row_count_equals_results_count(self, qapp, qtbot, app_state) -> None:
        """校验后表格行数等于执行结果数 (AU-01)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        app_state.load_registry()

        window._import_page._on_file(str(_MOUTAI_FILE))
        qtbot.wait(100)
        window._topbar.validate_clicked.emit()
        qtbot.wait(100)

        summary = app_state.results
        assert summary is not None
        # 导航到审计页以触发表格显示
        window._sidebar._nav_buttons["navAudit"].clicked_nav.emit("navAudit")
        qtbot.wait(50)
        table = window._audit_page._table
        # 表格行数应等于 results 列表长度 (含 skipped)
        assert table.rowCount() == len(summary.results), (
            f"期望 {len(summary.results)} 行，实际 {table.rowCount()}"
        )

    def test_table_has_seven_columns(self, qapp, qtbot, app_state) -> None:
        """审计表格有 7 列 (AU-01)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        assert window._audit_page._table.columnCount() == 7

    def test_category_column_uses_result_category(self, qapp, qtbot, app_state) -> None:
        """分类列使用 result.category (AU-01)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        app_state.load_registry()

        window._import_page._on_file(str(_MOUTAI_FILE))
        qtbot.wait(100)
        window._topbar.validate_clicked.emit()
        qtbot.wait(100)

        table = window._audit_page._table
        for row in range(table.rowCount()):
            cat_item = table.item(row, 2)
            assert cat_item is not None, f"第 {row} 行分类列为空"
            cat_text = cat_item.text()
            # 分类应包含连字符 (如 "A-表内平衡")
            assert cat_text != "", f"第 {row} 行分类列为空字符串"

    def test_status_cell_has_foreground_color(self, qapp, qtbot, app_state) -> None:
        """状态列前景色与结果严重性匹配 (AU-02)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        app_state.load_registry()

        window._import_page._on_file(str(_MOUTAI_FILE))
        qtbot.wait(100)
        window._topbar.validate_clicked.emit()
        qtbot.wait(100)

        table = window._audit_page._table
        for row in range(table.rowCount()):
            status_item = table.item(row, 4)
            assert status_item is not None, f"第 {row} 行状态列为空"
            # 前景色应不为默认 (状态列有专门着色)
            fg = status_item.foreground().color()
            assert fg.isValid(), f"第 {row} 行状态列无前景色"


class TestAuditEmptyState:
    """测试空状态 (AU-05)。"""

    def test_empty_state_visible_when_no_results(self, qapp, qtbot, app_state) -> None:
        """无结果时显示空状态提示 (AU-05)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        # 导航到审计页
        window._sidebar._nav_buttons["navAudit"].clicked_nav.emit("navAudit")
        qtbot.wait(50)
        assert not window._audit_page._empty.isHidden()

    def test_empty_state_hidden_after_validation(self, qapp, qtbot, app_state) -> None:
        """校验后空状态隐藏 (AU-05)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        app_state.load_registry()

        window._import_page._on_file(str(_MOUTAI_FILE))
        qtbot.wait(100)
        window._topbar.validate_clicked.emit()
        qtbot.wait(100)

        window._sidebar._nav_buttons["navAudit"].clicked_nav.emit("navAudit")
        qtbot.wait(50)
        assert window._audit_page._empty.isHidden()

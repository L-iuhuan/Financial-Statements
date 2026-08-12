"""历史页 (HistoryPage) 功能测试: HP-01..HP-05。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from fsa.gui.main_window import MainWindow
from fsa.gui.pages.history_page import HistoryCard

_TEST_ROOT = Path(__file__).resolve().parent
_PROJECT_ROOT = _TEST_ROOT.parent.parent
_MOUTAI_FILE = _PROJECT_ROOT / "tests" / "fixtures" / "real_reports" / "贵州茅台_2023年报_三大报表.xlsx"


class TestHistoryList:
    """测试历史列表 (HP-01, HP-02, HP-03)。"""

    def test_after_validation_history_card_shows_correct_stats(self, qapp, qtbot, app_state) -> None:
        """校验后历史页显示卡片且统计正确 (HP-01)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        app_state.load_registry()

        # 导入并校验
        window._import_page._on_file(str(_MOUTAI_FILE))
        qtbot.wait(100)
        window._topbar.validate_clicked.emit()
        qtbot.wait(100)
        summary = app_state.results
        assert summary is not None

        # 切换到历史页
        window._sidebar._nav_buttons["navHistory"].clicked_nav.emit("navHistory")
        qtbot.wait(100)

        # 历史页应显示卡片
        cards = window._history_page.findChildren(HistoryCard)
        assert len(cards) >= 1, "历史页应显示至少一张卡片"

        # 清理
        history_id = cards[0]._history_id
        app_state.history_repo.delete(history_id)

    def test_view_button_emits_view_requested(self, qapp, qtbot, app_state) -> None:
        """点击查看按钮发出 view_requested 信号 (HP-02)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        app_state.load_registry()

        # 导入并校验
        window._import_page._on_file(str(_MOUTAI_FILE))
        qtbot.wait(100)
        window._topbar.validate_clicked.emit()
        qtbot.wait(100)

        # 切换到历史页
        window._sidebar._nav_buttons["navHistory"].clicked_nav.emit("navHistory")
        qtbot.wait(100)

        cards = window._history_page.findChildren(HistoryCard)
        assert len(cards) >= 1

        view_requested_ids = []
        window._history_page.view_requested.connect(
            lambda hid: view_requested_ids.append(hid)
        )

        # 触发查看
        cards[0].view_clicked.emit(cards[0]._history_id)
        assert len(view_requested_ids) == 1
        assert view_requested_ids[0] == cards[0]._history_id

        # 清理
        app_state.history_repo.delete(cards[0]._history_id)

    def test_viewing_history_does_not_create_new_record(self, qapp, qtbot, app_state) -> None:
        """查看历史不创建新记录 (HP-03)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        app_state.load_registry()

        # 导入并校验
        window._import_page._on_file(str(_MOUTAI_FILE))
        qtbot.wait(100)
        window._topbar.validate_clicked.emit()
        qtbot.wait(100)

        repo = app_state.history_repo
        count_before = repo.count()

        records = repo.get_recent(limit=1)
        assert len(records) == 1
        history_id = records[0]["id"]

        # 查看历史 (persist=False)
        window._on_view_history(history_id)
        qtbot.wait(100)

        count_after = repo.count()
        assert count_after == count_before, (
            f"查看历史后记录数应不变: {count_before} → {count_after}"
        )

        # 清理
        repo.delete(history_id)


class TestHistoryDelete:
    """测试删除历史 (HP-04, HP-05)。"""

    def test_delete_confirmed_removes_record(self, qapp, qtbot, app_state, monkeypatch) -> None:
        """确认删除后记录被移除 (HP-04)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        app_state.load_registry()

        # 导入并校验
        window._import_page._on_file(str(_MOUTAI_FILE))
        qtbot.wait(100)
        window._topbar.validate_clicked.emit()
        qtbot.wait(100)

        repo = app_state.history_repo
        count_before = repo.count()
        assert count_before >= 1

        # 切换到历史页
        window._sidebar._nav_buttons["navHistory"].clicked_nav.emit("navHistory")
        qtbot.wait(100)

        cards = window._history_page.findChildren(HistoryCard)
        assert len(cards) >= 1
        history_id = cards[0]._history_id

        # 模拟确认删除
        monkeypatch.setattr(
            QMessageBox, "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
        )

        cards[0].delete_clicked.emit(history_id)
        qtbot.wait(100)

        count_after = repo.count()
        assert count_after == count_before - 1, (
            f"删除后记录数应减 1: {count_before} → {count_after}"
        )

    def test_delete_cancelled_preserves_record(self, qapp, qtbot, app_state, monkeypatch) -> None:
        """取消删除后记录保留 (HP-05)。"""
        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)
        app_state.load_registry()

        # 导入并校验
        window._import_page._on_file(str(_MOUTAI_FILE))
        qtbot.wait(100)
        window._topbar.validate_clicked.emit()
        qtbot.wait(100)

        repo = app_state.history_repo
        count_before = repo.count()
        assert count_before >= 1

        # 切换到历史页
        window._sidebar._nav_buttons["navHistory"].clicked_nav.emit("navHistory")
        qtbot.wait(100)

        cards = window._history_page.findChildren(HistoryCard)
        assert len(cards) >= 1
        history_id = cards[0]._history_id

        # 模拟取消删除
        monkeypatch.setattr(
            QMessageBox, "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.No,
        )

        cards[0].delete_clicked.emit(history_id)
        qtbot.wait(100)

        count_after = repo.count()
        assert count_after == count_before, (
            f"取消删除后记录数应不变: {count_before} → {count_after}"
        )

        # 清理
        repo.delete(history_id)


class TestHistoryEmptyState:
    """测试空状态 (HP-06)。"""

    def test_empty_state_shows_when_no_records(self, qapp, qtbot, app_state) -> None:
        """无记录时显示空状态 (HP-06)。"""
        # 清理所有历史记录以确保空状态
        repo = app_state.history_repo
        if repo is not None:
            records = repo.get_recent(limit=200)
            for r in records:
                repo.delete(r["id"])

        window = MainWindow(app_state, initial_dark=False, theme_mode="light")
        qtbot.addWidget(window)

        window._sidebar._nav_buttons["navHistory"].clicked_nav.emit("navHistory")
        qtbot.wait(100)

        assert not window._history_page._empty_container.isHidden()

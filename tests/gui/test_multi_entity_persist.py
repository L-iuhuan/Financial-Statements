"""B1-5 多主体批量校验结果落库 + MultiEntityResultDialog 基本渲染测试。"""

from __future__ import annotations

import sqlite3

from fsa.gui.pages.import_page import ImportPage
from fsa.gui.widgets.multi_entity_dialog import MultiEntityResultDialog
from fsa.services.multi_entity_service import EntityOutcome, MultiEntityResult
from tests.gui.helpers import make_result, make_summary


class _StubHistoryRepo:
    """记录 save 调用的历史仓储替身。"""

    def __init__(self, fail_first: bool = False) -> None:
        self.saved: list[object] = []
        self._fail_first = fail_first
        self._calls = 0

    def save(self, summary: object) -> int:
        self._calls += 1
        if self._fail_first and self._calls == 1:
            raise sqlite3.DatabaseError("磁盘错误")
        self.saved.append(summary)
        return len(self.saved)


def _make_result(entity_ids: list[str]) -> MultiEntityResult:
    """构造两个主体各带一份校验汇总的批量结果。"""
    outcomes = [
        EntityOutcome(
            entity_id=entity_id,
            folder=f"D:/data/{entity_id}",
            summary=make_summary([make_result()]),
        )
        for entity_id in entity_ids
    ]
    return MultiEntityResult(outcomes=outcomes, combined=make_summary([make_result()]), bilateral=[])


class TestPersistMultiEntityResults:
    """多主体结果写入历史记录。"""

    def test_each_entity_saved_with_folder_marker(self, qapp, qtbot, app_state) -> None:
        """每个主体的汇总都落库, source_files 带主体目录标识。"""
        stub = _StubHistoryRepo()
        app_state._history_repo = stub  # type: ignore[assignment]
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        # 页面构造时期间控件会写回当前月份, 需在构造后设置测试期间
        app_state.set_period("2024-12")
        result = _make_result(["甲公司", "乙公司"])

        saved = page._persist_multi_entity_results(result)

        assert saved == 2
        assert len(stub.saved) == 2
        first = stub.saved[0]
        assert "[主体:甲公司] D:/data/甲公司" in first.source_files  # type: ignore[attr-defined]
        assert first.period == "2024-12"  # type: ignore[attr-defined]

    def test_failure_does_not_interrupt(self, qapp, qtbot, app_state) -> None:
        """单个主体保存失败不中断其余主体落库。"""
        stub = _StubHistoryRepo(fail_first=True)
        app_state._history_repo = stub  # type: ignore[assignment]
        page = ImportPage(app_state)
        qtbot.addWidget(page)

        saved = page._persist_multi_entity_results(_make_result(["A", "B"]))

        assert saved == 1
        assert len(stub.saved) == 1

    def test_repo_unavailable_returns_zero(self, qapp, qtbot, app_state) -> None:
        """历史存储降级为 None 时跳过保存。"""
        app_state._history_repo = None
        page = ImportPage(app_state)
        qtbot.addWidget(page)

        assert page._persist_multi_entity_results(_make_result(["A"])) == 0

    def test_outcome_without_summary_skipped(self, qapp, qtbot, app_state) -> None:
        """校验失败的主体 (summary=None) 不产生历史记录。"""
        stub = _StubHistoryRepo()
        app_state._history_repo = stub  # type: ignore[assignment]
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        result = MultiEntityResult(
            outcomes=[EntityOutcome(entity_id="A", folder="fA", summary=None, errors=["读取失败"])]
        )

        assert page._persist_multi_entity_results(result) == 0


class TestMultiEntityResultDialog:
    """结果对话框基本渲染 (offscreen)。"""

    def test_dialog_renders_entity_rows(self, qapp, qtbot) -> None:
        """对话框按主体数渲染表格行。"""
        dialog = MultiEntityResultDialog(_make_result(["A", "B"]))
        qtbot.addWidget(dialog)

        from PySide6.QtWidgets import QTableWidget

        tables = dialog.findChildren(QTableWidget)
        assert tables
        assert tables[0].rowCount() == 2

    def test_saved_hint_shown_when_saved(self, qapp, qtbot) -> None:
        """传入 saved_count 时显示「结果已保存到历史记录」。"""
        from PySide6.QtWidgets import QLabel

        dialog = MultiEntityResultDialog(_make_result(["A"]), saved_count=1)
        qtbot.addWidget(dialog)

        texts = [label.text() for label in dialog.findChildren(QLabel)]
        assert any("结果已保存到历史记录" in text for text in texts)

    def test_saved_hint_absent_without_count(self, qapp, qtbot) -> None:
        """不传 saved_count 时不显示落库提示。"""
        from PySide6.QtWidgets import QLabel

        dialog = MultiEntityResultDialog(_make_result(["A"]))
        qtbot.addWidget(dialog)

        texts = [label.text() for label in dialog.findChildren(QLabel)]
        assert not any("结果已保存到历史记录" in text for text in texts)

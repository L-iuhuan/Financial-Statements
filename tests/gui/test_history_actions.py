"""历史页搜索(规则/状态)/批量删除/摘要导出测试。"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from fsa.core.models.result import ValidationSummary
from fsa.gui.pages.history_page import HistoryPage
from tests.gui.helpers import make_result


def _seed_two_records(app_state) -> None:
    repo = app_state.history_repo
    assert repo is not None
    repo.delete_all()
    failed = ValidationSummary(
        period="2024-12",
        total=1,
        passed=0,
        failed=1,
        errored=0,
        skipped=0,
        results=[make_result(rule_id="BS-BAL-001", passed=False, diff=10.0)],
        source_files=["a.xlsx"],
        source_hashes=["aa"],
        source_file_sizes=[2048],
    )
    repo.save(failed)
    errored = ValidationSummary(
        period="2025-01",
        total=1,
        passed=0,
        failed=0,
        errored=1,
        skipped=0,
        results=[make_result(rule_id="IS-TAX-001", passed=False, errored=True)],
        source_files=["b.xlsx"],
    )
    repo.save(errored)


class TestHistorySearchActions:
    def test_search_by_rule_id(self, qapp, qtbot, app_state) -> None:
        _seed_two_records(app_state)
        page = HistoryPage(app_state)
        qtbot.addWidget(page)
        page._load_history()
        assert len(page._cards) == 2

        page._search_input.setText("BS-BAL-001")
        qtbot.wait(20)
        assert len(page._cards) == 1

    def test_search_by_status(self, qapp, qtbot, app_state) -> None:
        _seed_two_records(app_state)
        page = HistoryPage(app_state)
        qtbot.addWidget(page)
        page._load_history()

        page._search_input.setText("异常")
        qtbot.wait(20)
        assert len(page._cards) == 1

    def test_export_summary_writes_json(self, qapp, qtbot, app_state, tmp_path: Path, monkeypatch) -> None:
        _seed_two_records(app_state)
        page = HistoryPage(app_state)
        qtbot.addWidget(page)
        page._load_history()

        target = tmp_path / "summary.json"
        monkeypatch.setattr(
            QFileDialog,
            "getSaveFileName",
            lambda *args, **kwargs: (str(target), "JSON 文件 (*.json)"),
        )
        page._export_summary()

        payload = json.loads(target.read_text(encoding="utf-8"))
        assert len(payload) == 2
        first = payload[-1]
        assert first["source_file_sizes"] == [2048]
        assert first["rule_version"] in ("", "1.3.0")

    def test_delete_all_confirmed(self, qapp, qtbot, app_state, monkeypatch) -> None:
        _seed_two_records(app_state)
        page = HistoryPage(app_state)
        qtbot.addWidget(page)
        page._load_history()

        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
        )
        page._delete_all_history()

        assert app_state.history_repo.count() == 0
        assert page._cards == []
        assert not page._delete_all_btn.isEnabled()

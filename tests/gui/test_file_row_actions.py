"""导入文件行内操作（移除/重试）测试。"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox, QPushButton

from fsa.core.models.detail import DetailDataset
from fsa.gui.pages.import_page import ImportPage
from fsa.gui.widgets.import_file_list import ImportFileList, ImportFileRow
from tests.gui.helpers import make_report


class TestFileRowRemove:
    """行内「移除」按钮测试。"""

    def test_remove_waiting_row_directly(self, qapp, qtbot) -> None:
        """waiting 状态行点击移除后直接消失。"""
        widget = ImportFileList()
        qtbot.addWidget(widget)
        widget.set_files(["/tmp/a.xlsx"])
        row = widget.findChildren(ImportFileRow)[0]
        remove_btn = cast(QPushButton, row._remove_btn)

        QTest.mouseClick(remove_btn, Qt.MouseButton.LeftButton)

        assert widget.findChildren(ImportFileRow) == []

    def test_remove_completed_row_confirms(self, qapp, qtbot, monkeypatch) -> None:
        """completed 状态行需确认后才移除。"""
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
        )
        widget = ImportFileList()
        qtbot.addWidget(widget)
        widget.set_files(["/tmp/a.xlsx"])
        widget.set_completed(0)
        row = widget.findChildren(ImportFileRow)[0]
        remove_btn = cast(QPushButton, row._remove_btn)

        QTest.mouseClick(remove_btn, Qt.MouseButton.LeftButton)

        assert widget.findChildren(ImportFileRow) == []

    def test_remove_completed_row_cancelled_keeps_row(self, qapp, qtbot, monkeypatch) -> None:
        """completed 状态行点击「否」后保留。"""
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.No,
        )
        widget = ImportFileList()
        qtbot.addWidget(widget)
        widget.set_files(["/tmp/a.xlsx"])
        widget.set_completed(0)
        row = widget.findChildren(ImportFileRow)[0]
        remove_btn = cast(QPushButton, row._remove_btn)

        QTest.mouseClick(remove_btn, Qt.MouseButton.LeftButton)

        assert len(widget.findChildren(ImportFileRow)) == 1


class TestFileRowRetry:
    """行内「重试」按钮测试。"""

    def test_retry_failed_row_becomes_completed(self, app_state, qtbot, monkeypatch) -> None:
        """failed 行点击重试, 读取成功后状态变为 completed。"""
        page = ImportPage(app_state)
        qtbot.addWidget(page)

        def fake_import(
            file_paths: list[str],
            progress_cb: object | None = None,
            event_cb: object | None = None,
            cancel_event: object | None = None,
        ) -> tuple[list, object, list[str]]:
            if callable(event_cb):
                event_cb({"kind": "started", "index": 0, "name": Path(file_paths[0]).name})
                event_cb({"kind": "completed", "index": 0})
            return [make_report()], DetailDataset(period="2024-12"), []

        monkeypatch.setattr(page, "_import_paths", fake_import)
        page._file_list.set_files(["a.xlsx"])
        page._file_list.set_failed(0, "a.xlsx: 文件不存在")
        row = page._file_list.findChildren(ImportFileRow)[0]
        retry_btn = cast(QPushButton, row._retry_btn)
        assert not retry_btn.isHidden()

        QTest.mouseClick(retry_btn, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: row.status() == "completed", timeout=2000)

        assert row.status() == "completed"

    def test_retry_failed_row_stays_failed(self, app_state, qtbot, monkeypatch) -> None:
        """failed 行点击重试后仍失败, 状态保持 failed 并更新原因。"""
        page = ImportPage(app_state)
        qtbot.addWidget(page)

        def fake_import(
            file_paths: list[str],
            progress_cb: object | None = None,
            event_cb: object | None = None,
            cancel_event: object | None = None,
        ) -> tuple[list, object, list[str]]:
            if callable(event_cb):
                event_cb({"kind": "started", "index": 0, "name": Path(file_paths[0]).name})
                event_cb({"kind": "failed", "index": 0, "reason": "a.xlsx: 格式错误"})
            return [], DetailDataset(period="2024-12"), ["a.xlsx: 格式错误"]

        monkeypatch.setattr(page, "_import_paths", fake_import)
        page._file_list.set_files(["a.xlsx"])
        page._file_list.set_failed(0, "a.xlsx: 文件不存在")
        row = page._file_list.findChildren(ImportFileRow)[0]
        retry_btn = cast(QPushButton, row._retry_btn)

        QTest.mouseClick(retry_btn, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(
            lambda: "格式错误" in row._status_label.text(), timeout=2000
        )

        assert row.status() == "failed"
        assert "格式错误" in row._status_label.text()

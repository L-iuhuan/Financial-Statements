"""导入文件列表 (ImportFileList) 与 ImportPage 集成测试。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from fsa.gui.pages.import_page import ImportPage
from fsa.gui.widgets.import_file_list import ImportFileList, ImportFileRow


class TestImportFileList:
    """ImportFileList 单元测试。"""

    def test_set_files_creates_rows_with_names(self, qapp, qtbot) -> None:
        """拖入多文件后列表行数与文件名正确。"""
        widget = ImportFileList()
        qtbot.addWidget(widget)
        widget.set_files(["/tmp/a.xlsx", "/tmp/b.pdf"])
        rows = widget.findChildren(ImportFileRow)
        assert len(rows) == 2
        assert rows[0]._name_label.text() == "a.xlsx"
        assert rows[1]._name_label.text() == "b.pdf"

    def test_initial_status_is_waiting(self, qapp, qtbot) -> None:
        """文件行初始状态为等待中。"""
        widget = ImportFileList()
        qtbot.addWidget(widget)
        widget.set_files(["a.xlsx"])
        row = widget.findChildren(ImportFileRow)[0]
        assert row.status() == "waiting"
        assert row._status_label.text() == "等待中"

    def test_status_flow_waiting_to_importing_to_completed(self, qapp, qtbot) -> None:
        """状态按等待 -> 导入中 -> 完成流转。"""
        widget = ImportFileList()
        qtbot.addWidget(widget)
        widget.set_files(["a.xlsx"])
        widget.set_importing(0)
        row = widget.findChildren(ImportFileRow)[0]
        assert row.status() == "importing"
        assert row._status_label.text() == "导入中"
        widget.set_completed(0)
        assert row.status() == "completed"
        assert row._status_label.text() == "完成"

    def test_failed_status_shows_reason(self, qapp, qtbot) -> None:
        """失败文件显示红叉与中文原因摘要。"""
        widget = ImportFileList()
        qtbot.addWidget(widget)
        widget.set_files(["a.xlsx"])
        widget.set_failed(0, "/tmp/a.xlsx: 文件不存在")
        row = widget.findChildren(ImportFileRow)[0]
        assert row.status() == "failed"
        assert "失败" in row._status_label.text()
        assert "文件不存在" in row._status_label.text()

    def test_finish_batch_shows_summary_and_start_button(self, qapp, qtbot) -> None:
        """全部完成后显示汇总与醒目的开始校验按钮。"""
        widget = ImportFileList()
        qtbot.addWidget(widget)
        widget.set_files(["a.xlsx", "b.xlsx"])
        widget.set_completed(0)
        widget.set_completed(1)
        widget.finish_batch(3, 120)
        assert "共 2 个文件" in widget._summary_label.text()
        assert "3 张报表" in widget._summary_label.text()
        assert "120 行明细" in widget._summary_label.text()
        assert widget._start_btn.isVisible()

    def test_finish_batch_hides_start_button_when_no_data(self, qapp, qtbot) -> None:
        """无有效数据时隐藏开始校验按钮。"""
        widget = ImportFileList()
        qtbot.addWidget(widget)
        widget.set_files(["a.xlsx"])
        widget.set_failed(0, "文件无法解析")
        widget.finish_batch(0, 0)
        assert not widget._start_btn.isVisible()

    def test_start_button_emits_signal(self, qapp, qtbot) -> None:
        """点击开始校验按钮发出 start_validate_clicked 信号。"""
        widget = ImportFileList()
        qtbot.addWidget(widget)
        widget.set_files(["a.xlsx"])
        widget.set_completed(0)
        widget.finish_batch(1, 10)
        signals: list[int] = []
        widget.start_validate_clicked.connect(lambda: signals.append(1))
        QTest.mouseClick(widget._start_btn, Qt.MouseButton.LeftButton)
        assert signals == [1]

    def test_clear_removes_rows_and_hides_button(self, qapp, qtbot) -> None:
        """清空后列表隐藏、行从布局移除、按钮隐藏。"""
        widget = ImportFileList()
        qtbot.addWidget(widget)
        widget.set_files(["a.xlsx"])
        widget.set_completed(0)
        widget.finish_batch(1, 10)
        widget.clear()
        rows_layout = widget._rows_container.layout()
        assert rows_layout is not None
        assert rows_layout.count() == 0
        assert not widget._start_btn.isVisible()
        assert not widget._summary_label.isVisible()
        assert not widget.isVisible()


class TestImportPageFileList:
    """ImportPage 与 ImportFileList 集成测试。"""

    def test_drop_files_populates_file_list(self, app_state, qtbot) -> None:
        """拖入文件后 ImportPage 的文件列表出现对应行。"""
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        page._file_list.set_files(["a.xlsx", "b.xlsx"])
        rows = page._file_list.findChildren(ImportFileRow)
        assert len(rows) == 2

    def test_reset_clears_file_list(self, app_state, qtbot) -> None:
        """重置/清空报表后文件列表被清空。"""
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        page._file_list.set_files(["a.xlsx"])
        page._file_list.set_completed(0)
        page._file_list.finish_batch(1, 10)
        app_state.set_reports([])
        qtbot.wait(50)
        rows_layout = page._file_list._rows_container.layout()
        assert rows_layout is not None
        assert rows_layout.count() == 0
        assert not page._file_list._start_btn.isVisible()

    def test_start_button_wired_to_validate_async(self, app_state, qtbot) -> None:
        """文件列表的开始校验按钮点击会触发 ImportPage 的校验入口。"""
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        page._file_list.set_files(["a.xlsx"])
        page._file_list.set_completed(0)
        page._file_list.finish_batch(1, 10)
        calls: list[int] = []
        page.trigger_validate_async = lambda: calls.append(1)  # type: ignore[method-assign]
        QTest.mouseClick(page._file_list._start_btn, Qt.MouseButton.LeftButton)
        assert calls == [1]

    def test_async_import_updates_row_states(self, app_state, qtbot, monkeypatch) -> None:
        """后台导入过程中文件行状态会更新为导入中/完成。"""
        page = ImportPage(app_state)
        qtbot.addWidget(page)

        def fake_import(
            file_paths: list[str],
            progress_cb: object | None = None,
            event_cb: object | None = None,
            cancel_event: object | None = None,
        ) -> tuple[list, object, list[str]]:
            from fsa.core.models.detail import DetailDataset

            if callable(event_cb):
                event_cb({"kind": "started", "index": 0, "name": "a.xlsx"})
                event_cb({"kind": "completed", "index": 0})
            return [], DetailDataset(period="2024-12"), []

        monkeypatch.setattr(page, "_import_paths", fake_import)
        page._on_files_async(["a.xlsx"])
        qtbot.wait(100)
        row = page._file_list.findChildren(ImportFileRow)[0]
        assert row.status() == "completed"

    def test_async_import_failed_updates_row_with_reason(self, app_state, qtbot, monkeypatch) -> None:
        """后台导入失败后文件行显示失败原因。"""
        page = ImportPage(app_state)
        qtbot.addWidget(page)

        def fake_import(
            file_paths: list[str],
            progress_cb: object | None = None,
            event_cb: object | None = None,
            cancel_event: object | None = None,
        ) -> tuple[list, object, list[str]]:
            from fsa.core.models.detail import DetailDataset

            if callable(event_cb):
                event_cb({"kind": "started", "index": 0, "name": "a.xlsx"})
                event_cb({"kind": "failed", "index": 0, "reason": "a.xlsx: 文件不存在"})
            return [], DetailDataset(period="2024-12"), ["a.xlsx: 文件不存在"]

        monkeypatch.setattr(page, "_import_paths", fake_import)
        page._on_files_async(["a.xlsx"])
        qtbot.wait(100)
        row = page._file_list.findChildren(ImportFileRow)[0]
        assert row.status() == "failed"
        assert "文件不存在" in row._status_label.text()

    def test_batch_exception_finalizes_all_rows(self, app_state, qtbot, monkeypatch) -> None:
        """回归: 批量导入整体异常时, 未到终态的行收尾为失败, 不再卡在导入中。"""
        page = ImportPage(app_state)
        qtbot.addWidget(page)

        def raising_import(
            file_paths: list[str],
            progress_cb: object | None = None,
            event_cb: object | None = None,
            cancel_event: object | None = None,
        ) -> tuple[list, object, list[str]]:
            if callable(event_cb):
                # 第一个文件开始了但永远等不到完成事件 (模拟异常逃逸)
                event_cb({"kind": "started", "index": 0, "name": "a.xlsx"})
            raise RuntimeError("模拟批量异常")

        monkeypatch.setattr(page, "_import_paths", raising_import)
        page._on_files_async(["a.xlsx", "b.xlsx"])
        # 页面未 show 时 isVisible() 恒 False, 用 isHidden() 判断显隐意图
        qtbot.waitUntil(
            lambda: not page._file_list._summary_label.isHidden(), timeout=3000
        )
        rows = page._file_list.findChildren(ImportFileRow)
        assert all(row.status() == "failed" for row in rows), \
            f"存在未收尾的行: {[row.status() for row in rows]}"
        assert "中止" in page._file_list._summary_label.text()
        assert not page._file_list._start_btn.isVisible()
        assert page._import_cancel_event is None, "批次结束后运行态应复位"


class TestImportFileListFailureFinalize:
    """fail_all_pending 收尾逻辑单元测试 (2026-09-17 卡死回归)。"""

    def test_fail_all_pending_marks_stuck_rows(self, qapp, qtbot) -> None:
        """导入中/等待中的行全部标记失败, 汇总含中止字样, 按钮隐藏。"""
        widget = ImportFileList()
        qtbot.addWidget(widget)
        widget.set_files(["a.xlsx", "b.xlsx", "c.xlsx"])
        widget.set_importing(0)
        widget.set_completed(1)  # b 已完成, 收尾不应覆盖
        widget.fail_all_pending("Excel 进程异常退出")
        rows = widget.findChildren(ImportFileRow)
        assert rows[0].status() == "failed"
        assert rows[1].status() == "completed"
        assert rows[2].status() == "failed"
        assert "中止" in widget._summary_label.text()
        assert "2 个文件未完成" in widget._summary_label.text()
        assert not widget._start_btn.isVisible()

    def test_fail_all_pending_all_terminal_shows_plain_failure(self, qapp, qtbot) -> None:
        """全部行已到终态时, 汇总显示普通失败而非中止。"""
        widget = ImportFileList()
        qtbot.addWidget(widget)
        widget.set_files(["a.xlsx"])
        widget.set_failed(0, "文件不存在")
        widget.fail_all_pending("批量异常")
        assert "导入失败" in widget._summary_label.text()


class TestOverflowAndInfoBarFixes:
    """2026-09-17 实测缺陷回归: 行溢出 + InfoBar 叠加 + 按钮防连点。"""

    def test_long_filename_elided_not_overflow(self, qapp, qtbot) -> None:
        """超长文件名在窄容器中截断显示省略号, 不撑破行宽。"""
        widget = ImportFileList()
        qtbot.addWidget(widget)
        long_name = (
            "附表2：厦门拓尔微电子有限公司-带辅助核算的科目余额表、"
            "序时账及现金流量明细表20260531.xls"
        )
        widget.show()
        widget.set_files([long_name])
        widget.resize(360, 200)
        row = widget.findChildren(ImportFileRow)[0]
        row.show()  # 隐藏控件的 resize 事件被 Qt 延迟, 可见时同步派发
        row.resize(320, 40)
        assert "…" in row._name_label.text()
        assert row._name_label.toolTip() == long_name, "全名应保留在 tooltip"
        assert row.width() <= 360, "行宽不应超过容器"

    def test_failed_reason_elided_with_tooltip(self, qapp, qtbot) -> None:
        """超长失败原因截断显示, 完整原因在 tooltip。"""
        widget = ImportFileList()
        qtbot.addWidget(widget)
        full_reason = "a.xlsx: " + "异常信息段落" * 50
        widget.set_files(["a.xlsx"])
        widget.set_failed(0, full_reason)
        row = widget.findChildren(ImportFileRow)[0]
        assert "…" in row._status_label.text(), "长原因应省略号截断"
        assert "异常信息段落" in row._status_label.toolTip(), "完整原因在 tooltip"
        assert row._status_label.maximumWidth() == 320

    def test_validate_running_disables_start_button(self, qapp, qtbot) -> None:
        """校验进行期间「开始校验」按钮禁用, 结束后恢复。"""
        widget = ImportFileList()
        qtbot.addWidget(widget)
        widget.set_files(["a.xlsx"])
        widget.set_completed(0)
        widget.finish_batch(1, 10)
        assert widget._start_btn.isEnabled()
        widget.set_validate_running(True)
        assert not widget._start_btn.isEnabled()
        widget.set_validate_running(False)
        assert widget._start_btn.isEnabled()

    def test_show_info_single_instance_closes_previous(
        self, qapp, qtbot, app_state, monkeypatch
    ) -> None:
        """连续两次 _show_info: 上一条被关闭, 同屏只保留一条。"""
        import fsa.gui.pages.import_page_results as results_mod

        created: list = []

        class _FakeInfoBar:
            def __init__(self) -> None:
                self.closed = False
                created.append(self)

            def close(self) -> None:
                self.closed = True

            @staticmethod
            def _factory(title: str, message: str, **kwargs: object) -> _FakeInfoBar:
                return _FakeInfoBar()

            success = staticmethod(_factory)
            warning = staticmethod(_factory)
            error = staticmethod(_factory)
            info = staticmethod(_factory)

        monkeypatch.setattr(results_mod, "InfoBar", _FakeInfoBar)
        page = ImportPage(app_state)
        qtbot.addWidget(page)
        page._show_info("第一条提示", "success")
        page._show_info("第二条提示", "warning")
        assert len(created) == 2
        assert created[0].closed, "第一条应在新条弹出前被关闭"
        assert not created[1].closed

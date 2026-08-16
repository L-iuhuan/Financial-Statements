"""导入页批量导入测试: 单文件失败不中断整批，失败文件数据不入结果。

覆盖审查报告 #5（批量导入中断）与 #6（dataset 半状态）修复。
使用 pytest-qt 的 qapp 提供 Qt 应用环境，构造真实 ImportPage 实例，
通过 monkeypatch 注入受控的导入行为。

注：自单次读取重构后，_on_files 先调用 read_excel/read_pdf 读取文件，
再分别调用 import_data；因此测试需 monkeypatch 读取函数与 import_data 方法。
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fsa.core.models.detail import DetailDataset, JournalRow, TrialBalanceRow
from fsa.core.models.report import Report, ReportType
from fsa.gui.app_state import AppState
from fsa.gui.pages.import_page import ImportPage


def _make_page() -> tuple[ImportPage, AppState]:
    """创建独立的 ImportPage 与 AppState。"""
    state = AppState()
    page = ImportPage(state)
    return page, state


def _balance_sheet_report(file_path: str) -> Report:
    from tests.conftest import make_balance_sheet

    report = make_balance_sheet(asset_total=100.0, liability_total=60.0, equity_total=40.0)
    report.source_file = file_path
    return report


def _cash_flow_report(file_path: str) -> Report:
    from tests.conftest import make_cash_flow_statement

    report = make_cash_flow_statement(operating_net=500.0)
    report.source_file = file_path
    return report


class TestBatchImportIsolation:
    """测试批量导入的单文件失败隔离（#5）。"""

    def test_third_file_still_processed_after_middle_keyerror(self, qapp, monkeypatch) -> None:
        """三文件导入（正常/触发 KeyError/正常）：第三个文件仍被处理。"""
        page, state = _make_page()

        # 读取步骤：全部成功，返回空数据（import_data 被 mock 覆盖）
        monkeypatch.setattr(
            "fsa.gui.pages.import_page.read_excel",
            lambda file_path, use_com=False: {},
        )

        def fake_import_main_data(data: dict, source_file: str, suffix: str) -> list[Report]:
            if source_file == "bad.xlsx":
                raise KeyError("缺失列")
            if source_file == "a.xlsx":
                return [_balance_sheet_report(source_file)]
            return [_cash_flow_report(source_file)]

        def fake_import_detail_data(data: dict) -> DetailDataset:
            ds = DetailDataset()
            # 用占位符区分来源（source_file 由调用方设置）
            ds.journal.append(
                JournalRow(
                    date="2026-06-30",
                    voucher_no="记-0001",
                    parent_account="",
                    account_code="1002",
                    account_name="银行存款",
                    summary="收款",
                    direction="贷",
                    amount=500.0,
                )
            )
            return ds

        messages: list[tuple[str, str]] = []
        page._importer.import_data = fake_import_main_data
        page._detail_importer.import_data = fake_import_detail_data
        page._show_info = lambda message, kind="info": messages.append((message, kind))

        page._on_files(["a.xlsx", "bad.xlsx", "c.xlsx"])

        # 第一个与第三个文件的主表均被导入，第二个被跳过
        types = {r.report_type for r in state.reports}
        assert ReportType.BALANCE_SHEET in types
        assert ReportType.CASH_FLOW_STATEMENT in types
        assert len(state.reports) == 2

        # 第一个与第三个文件的明细数据均进入 dataset
        ds = state.detail_dataset
        assert ds is not None
        assert len(ds.journal) == 3  # 3 个文件各 1 行

        # 中文提示包含成功/失败文件数
        assert messages
        message, kind = messages[-1]
        # 审查后行为修正 (2026-08-16 终审 P2): 主表导入失败的文件计入失败,
        # 不再静默计入成功 (此前断言 kind=="success" 与「成功导入 3 个文件」)
        assert "成功导入 2 个文件" in message
        assert "1 个文件导入失败：bad.xlsx" in message
        assert kind == "warning"
        # 失败文件进入重试清单
        assert page._retry_failed_paths == ["bad.xlsx"]

    def test_failed_file_detail_not_merged(self, qapp, monkeypatch) -> None:
        """失败文件（读取层面）的明细数据不进入 dataset（#6）。"""
        page, state = _make_page()

        # 读取步骤：good 成功，bad 失败
        def fake_read_excel(file_path: str, use_com: bool = False) -> dict:
            if file_path == "bad.xlsx":
                raise TypeError("错误的列类型")
            return {}

        monkeypatch.setattr("fsa.gui.pages.import_page.read_excel", fake_read_excel)

        def fake_import_main_data(data: dict, source_file: str, suffix: str) -> list[Report]:
            return [_balance_sheet_report(source_file)]

        def fake_import_detail_data(data: dict) -> DetailDataset:
            ds = DetailDataset()
            ds.trial_balance.append(TrialBalanceRow(account_code="1002", account_name="银行存款", ending_debit=999.0))
            return ds

        page._importer.import_data = fake_import_main_data
        page._detail_importer.import_data = fake_import_detail_data

        page._on_files(["good.xlsx", "bad.xlsx"])

        ds = state.detail_dataset
        assert ds is not None
        # 只含成功文件的数据
        assert len(ds.trial_balance) == 1
        assert ds.trial_balance[0].ending_debit == 999.0
        # 主表仅来自成功文件
        assert len(state.reports) == 1
        assert state.reports[0].source_file == "good.xlsx"

    def test_all_files_success_shows_success_message(self, qapp, monkeypatch) -> None:
        """全部成功时显示成功提示且不含失败计数。"""
        page, state = _make_page()

        monkeypatch.setattr(
            "fsa.gui.pages.import_page.read_excel",
            lambda file_path, use_com=False: {},
        )

        def fake_import_main_data(data: dict, source_file: str, suffix: str) -> list[Report]:
            return [_balance_sheet_report(source_file)]

        def fake_import_detail_data(data: dict) -> DetailDataset:
            return DetailDataset()

        messages: list[tuple[str, str]] = []
        page._importer.import_data = fake_import_main_data
        page._detail_importer.import_data = fake_import_detail_data
        page._show_info = lambda message, kind="info": messages.append((message, kind))

        page._on_files(["a.xlsx", "b.xlsx"])

        assert messages
        message, kind = messages[-1]
        assert "成功导入 2 个文件" in message
        assert "失败" not in message
        assert kind == "success"

    def test_detail_import_failure_counts_as_failed(self, qapp, monkeypatch) -> None:
        """审查后行为修正 (终审 P2): 明细导入失败的文件同样计入失败, 不静默成功。"""
        page, state = _make_page()

        monkeypatch.setattr(
            "fsa.gui.pages.import_page.read_excel",
            lambda file_path, use_com=False: {},
        )

        def fake_import_main_data(data: dict, source_file: str, suffix: str) -> list[Report]:
            return [_balance_sheet_report(source_file)]

        def fake_import_detail_data(data: dict) -> DetailDataset:
            raise ValueError("明细格式错误")

        messages: list[tuple[str, str]] = []
        page._importer.import_data = fake_import_main_data
        page._detail_importer.import_data = fake_import_detail_data
        page._show_info = lambda message, kind="info": messages.append((message, kind))

        page._on_files(["a.xlsx", "b.xlsx"])

        message, kind = messages[-1]
        assert "成功导入 0 个文件" in message
        assert "2 个文件导入失败：a.xlsx、b.xlsx（详情见日志）" in message
        assert kind == "warning"
        # 主表仍导入成功 (明细失败不影响主表), 但文件计入失败可重试
        assert len(state.reports) == 1
        assert sorted(page._retry_failed_paths) == ["a.xlsx", "b.xlsx"]

    def test_keyerror_message_contains_filename(self, qapp, monkeypatch) -> None:
        """单文件读取失败的错误信息包含文件名（#5）。"""
        page, state = _make_page()

        def fake_read_excel(
            file_path: str,
            use_com: bool = False,  # noqa: ARG001
        ) -> dict:
            raise KeyError("缺失列")

        monkeypatch.setattr("fsa.gui.pages.import_page.read_excel", fake_read_excel)

        messages: list[tuple[str, str]] = []
        page._show_info = lambda message, kind="info": messages.append((message, kind))

        page._on_files(["only_bad.xlsx"])

        assert messages
        message, _ = messages[-1]
        assert "only_bad.xlsx" in message
        # 唯一文件失败 → 无报表，早退提示
        assert len(state.reports) == 0


class TestSingleReadPerFile:
    """验证单次读取重构：每个文件只调用一次 read_excel。"""

    def test_read_excel_called_once_per_file(self, qapp, monkeypatch) -> None:
        """每个文件只调用一次 read_excel，同时服务主表与明细导入。"""
        from fsa.core.importer import excel_reader

        call_count = 0
        original = excel_reader.read_excel

        def counting_read_excel(file_path: str, use_com: bool = False) -> dict:
            nonlocal call_count
            call_count += 1
            return original(file_path, use_com)

        # 替换模块级引用——import_page 已通过 from-import 持有引用，
        # 但 monkeypatch 替换模块属性会更新所有通过模块访问的调用方。
        # 为保险起见，同时替换 import_page 中的引用。
        monkeypatch.setattr(excel_reader, "read_excel", counting_read_excel)
        monkeypatch.setattr("fsa.gui.pages.import_page.read_excel", counting_read_excel)

        from tests.importer.conftest import make_balance_sheet_excel

        path = make_balance_sheet_excel()

        page, state = _make_page()
        page._on_files([str(path)])

        assert call_count == 1, f"read_excel 被调用了 {call_count} 次，应为 1 次"
        assert len(state.reports) == 1
        assert state.reports[0].report_type == ReportType.BALANCE_SHEET

    def test_read_excel_called_once_per_file_with_multiple_files(self, qapp, monkeypatch) -> None:
        """批量导入多个文件时，每个文件仍只调用一次 read_excel。"""
        from fsa.core.importer import excel_reader

        call_count = 0
        original = excel_reader.read_excel

        def counting_read_excel(
            file_path: str,
            use_com: bool = False,  # noqa: ARG001
        ) -> dict:
            nonlocal call_count
            call_count += 1
            return original(file_path, use_com)

        monkeypatch.setattr(excel_reader, "read_excel", counting_read_excel)
        monkeypatch.setattr("fsa.gui.pages.import_page.read_excel", counting_read_excel)

        from tests.importer.conftest import (
            make_balance_sheet_excel,
            make_income_statement_excel,
        )

        path1 = make_balance_sheet_excel()
        path2 = make_income_statement_excel()

        page, state = _make_page()
        page._on_files([str(path1), str(path2)])

        assert call_count == 2, f"read_excel 被调用了 {call_count} 次，应为 2 次（每个文件一次）"
        assert len(state.reports) == 2


class TestPdfImportHint:
    """PDF 导入完成后的只读扫描识别提示 (Phase B)。"""

    def test_pdf_diagnostics_shown_as_warning(self, qapp, monkeypatch) -> None:
        page, state = _make_page()
        captured: list[tuple[str, str]] = []

        def fake_show_info(message: str, kind: str) -> None:
            captured.append((message, kind))

        monkeypatch.setattr(page, "_show_info", fake_show_info)
        report = _balance_sheet_report("资产负债表.pdf")
        report.parse_diagnostics = "PDF 共 2 页、检测到 1 个表格；解析置信度: 高"

        page._apply_import_result(
            ["资产负债表.pdf"],
            [report],
            DetailDataset(period="2024-12"),
            [],
        )

        assert len(captured) == 1
        message, kind = captured[0]
        assert "建议优先使用 Excel" in message
        assert "解析诊断" in message
        assert kind == "warning"


class TestFailureMessageConcise:
    """V4: 导入失败提示精简 (文件名清单 + 详情见日志, 不含原始异常/长路径)。"""

    def test_partial_failure_message_lists_filenames_only(self, qapp, monkeypatch) -> None:
        """部分失败: 提示含失败数量与文件名, 不含原始错误详情。"""
        page, state = _make_page()
        messages: list[tuple[str, str]] = []
        page._show_info = lambda message, kind="info": messages.append((message, kind))
        report = _balance_sheet_report("a.xlsx")

        page._apply_import_result(
            ["a.xlsx", "b.xlsx"],
            [report],
            DetailDataset(period="2024-12"),
            ["b.xlsx: 文件不存在或已被占用"],
        )

        message, kind = messages[-1]
        assert kind == "warning"
        assert "1 个文件导入失败：b.xlsx（详情见日志）" in message
        assert "文件不存在或已被占用" not in message

    def test_all_failed_message_lists_filenames_only(self, qapp, monkeypatch) -> None:
        """全部失败: 早退提示同样精简。"""
        page, state = _make_page()
        messages: list[tuple[str, str]] = []
        page._show_info = lambda message, kind="info": messages.append((message, kind))

        page._apply_import_result(
            ["a.xlsx", "b.xlsx"],
            [],
            DetailDataset(period="2024-12"),
            ["a.xlsx: 读取失败", "b.xlsx: 读取失败"],
        )

        message, kind = messages[-1]
        assert kind == "warning"
        assert message == "2 个文件导入失败：a.xlsx、b.xlsx（详情见日志）"

    def test_more_than_three_failures_summarized(self, qapp, monkeypatch) -> None:
        """超过 3 个失败文件: 以「等 N 个文件」概括, 避免刷屏。"""
        page, state = _make_page()
        messages: list[tuple[str, str]] = []
        page._show_info = lambda message, kind="info": messages.append((message, kind))
        files = ["a.xlsx", "b.xlsx", "c.xlsx", "d.xlsx", "e.xlsx"]

        page._apply_import_result(
            files,
            [],
            DetailDataset(period="2024-12"),
            [f"{f}: 读取失败" for f in files],
        )

        message, kind = messages[-1]
        assert message == "5 个文件导入失败：a.xlsx、b.xlsx、c.xlsx 等 5 个文件（详情见日志）"


class TestRetryFailedFiles:
    """导入失败后可仅重试失败文件 (A4)。"""

    def test_partial_failure_shows_retry_button(self, qapp, qtbot, monkeypatch) -> None:
        page, state = _make_page()
        qtbot.addWidget(page)
        called: list[list[str]] = []
        monkeypatch.setattr(page, "_on_files_async", called.append)
        report = _balance_sheet_report("a.xlsx")

        page._apply_import_result(
            ["a.xlsx", "b.xlsx"],
            [report],
            DetailDataset(period="2024-12"),
            ["b.xlsx: 文件不存在"],
        )

        assert not page._retry_failed_btn.isHidden()
        page._retry_failed_btn.click()
        assert called == [["b.xlsx"]]
        assert page._retry_failed_btn.isHidden()

    def test_all_failed_still_shows_retry_button(self, qapp, qtbot, monkeypatch) -> None:
        page, state = _make_page()
        qtbot.addWidget(page)
        called: list[list[str]] = []
        monkeypatch.setattr(page, "_on_files_async", called.append)

        page._apply_import_result(
            ["a.xlsx", "b.xlsx"],
            [],
            DetailDataset(period="2024-12"),
            ["a.xlsx: 读取失败", "b.xlsx: 读取失败"],
        )

        assert not page._retry_failed_btn.isHidden()
        page._retry_failed_btn.click()
        assert called == [["a.xlsx", "b.xlsx"]]

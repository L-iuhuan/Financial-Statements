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

    def test_third_file_still_processed_after_middle_keyerror(
        self, qapp, monkeypatch
    ) -> None:
        """三文件导入（正常/触发 KeyError/正常）：第三个文件仍被处理。"""
        page, state = _make_page()

        # 读取步骤：全部成功，返回空数据（import_data 被 mock 覆盖）
        monkeypatch.setattr(
            "fsa.gui.pages.import_page.read_excel",
            lambda file_path, use_com=False: {},
        )

        def fake_import_main_data(
            data: dict, source_file: str, suffix: str
        ) -> list[Report]:
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
                    date="2026-06-30", voucher_no="记-0001", parent_account="",
                    account_code="1002", account_name="银行存款", summary="收款",
                    direction="贷", amount=500.0,
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
        assert "成功导入 3 个文件" in message
        assert "0 个文件失败" not in message.replace("成功导入 3 个文件", "")
        # bad.xlsx 的读取成功但 import_data 失败，主表被跳过，明细仍成功
        assert kind == "success"

    def test_failed_file_detail_not_merged(self, qapp, monkeypatch) -> None:
        """失败文件（读取层面）的明细数据不进入 dataset（#6）。"""
        page, state = _make_page()

        # 读取步骤：good 成功，bad 失败
        def fake_read_excel(
            file_path: str, use_com: bool = False
        ) -> dict:
            if file_path == "bad.xlsx":
                raise TypeError("错误的列类型")
            return {}

        monkeypatch.setattr(
            "fsa.gui.pages.import_page.read_excel", fake_read_excel
        )

        def fake_import_main_data(
            data: dict, source_file: str, suffix: str
        ) -> list[Report]:
            return [_balance_sheet_report(source_file)]

        def fake_import_detail_data(data: dict) -> DetailDataset:
            ds = DetailDataset()
            ds.trial_balance.append(
                TrialBalanceRow(
                    account_code="1002", account_name="银行存款", ending_debit=999.0
                )
            )
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

        def fake_import_main_data(
            data: dict, source_file: str, suffix: str
        ) -> list[Report]:
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

    def test_keyerror_message_contains_filename(self, qapp, monkeypatch) -> None:
        """单文件读取失败的错误信息包含文件名（#5）。"""
        page, state = _make_page()

        def fake_read_excel(
            file_path: str, use_com: bool = False  # noqa: ARG001
        ) -> dict:
            raise KeyError("缺失列")

        monkeypatch.setattr(
            "fsa.gui.pages.import_page.read_excel", fake_read_excel
        )

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

    def test_read_excel_called_once_per_file(
        self, qapp, monkeypatch
    ) -> None:
        """每个文件只调用一次 read_excel，同时服务主表与明细导入。"""
        from fsa.core.importer import excel_reader

        call_count = 0
        original = excel_reader.read_excel

        def counting_read_excel(
            file_path: str, use_com: bool = False
        ) -> dict:
            nonlocal call_count
            call_count += 1
            return original(file_path, use_com)

        # 替换模块级引用——import_page 已通过 from-import 持有引用，
        # 但 monkeypatch 替换模块属性会更新所有通过模块访问的调用方。
        # 为保险起见，同时替换 import_page 中的引用。
        monkeypatch.setattr(excel_reader, "read_excel", counting_read_excel)
        monkeypatch.setattr(
            "fsa.gui.pages.import_page.read_excel", counting_read_excel
        )

        from tests.importer.conftest import make_balance_sheet_excel

        path = make_balance_sheet_excel()

        page, state = _make_page()
        page._on_files([str(path)])

        assert call_count == 1, f"read_excel 被调用了 {call_count} 次，应为 1 次"
        assert len(state.reports) == 1
        assert state.reports[0].report_type == ReportType.BALANCE_SHEET

    def test_read_excel_called_once_per_file_with_multiple_files(
        self, qapp, monkeypatch
    ) -> None:
        """批量导入多个文件时，每个文件仍只调用一次 read_excel。"""
        from fsa.core.importer import excel_reader

        call_count = 0
        original = excel_reader.read_excel

        def counting_read_excel(
            file_path: str, use_com: bool = False  # noqa: ARG001
        ) -> dict:
            nonlocal call_count
            call_count += 1
            return original(file_path, use_com)

        monkeypatch.setattr(excel_reader, "read_excel", counting_read_excel)
        monkeypatch.setattr(
            "fsa.gui.pages.import_page.read_excel", counting_read_excel
        )

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
